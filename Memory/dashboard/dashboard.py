import os
import streamlit as st
from neo4j import GraphDatabase
from pyvis.network import Network
import streamlit.components.v1 as components
import pandas as pd
import chromadb
from chromadb.utils import embedding_functions
from neo4j.graph import Node, Relationship
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import colorsys
import hashlib
import re
from datetime import datetime, timedelta, date
import time
import json
from collections import defaultdict
import math

# Beautiful color palettes for node visualization
MATERIAL_PALETTE = [
    "#F44336",  # Red
    "#E91E63",  # Pink
    "#9C27B0",  # Purple
    "#673AB7",  # Deep Purple
    "#3F51B5",  # Indigo
    "#2196F3",  # Blue
    "#03A9F4",  # Light Blue
    "#00BCD4",  # Cyan
    "#009688",  # Teal
    "#4CAF50",  # Green
    "#8BC34A",  # Light Green
    "#CDDC39",  # Lime
    "#FFEB3B",  # Yellow
    "#FFC107",  # Amber
    "#FF9800",  # Orange
    "#FF5722",  # Deep Orange
]

PASTEL_PALETTE = [
    "#FFB3BA",  # Light Pink
    "#FFDFBA",  # Light Orange
    "#FFFFBA",  # Light Yellow
    "#BAFFC9",  # Light Green
    "#BAE1FF",  # Light Blue
    "#E6BAFF",  # Light Purple
    "#FFB3E6",  # Light Magenta
    "#C9BAFF",  # Light Violet
    "#BAFFFF",  # Light Cyan
    "#D4FFBA",  # Mint Green
    "#FFCBA4",  # Peach
    "#F0B3FF",  # Lavender
]

VIBRANT_PALETTE = [
    "#FF6B6B",  # Coral
    "#4ECDC4",  # Turquoise
    "#45B7D1",  # Sky Blue
    "#96CEB4",  # Mint
    "#FFEAA7",  # Banana
    "#DDA0DD",  # Plum
    "#98D8C8",  # Seafoam
    "#F7DC6F",  # Lemon
    "#BB8FCE",  # Orchid
    "#85C1E9",  # Powder Blue
    "#F8C471",  # Apricot
    "#82E0AA",  # Spring Green
]


def generate_color_from_string(text: str, palette: List[str] = MATERIAL_PALETTE) -> str:
    """Generate a consistent color for a string using a hash-based approach"""
    hash_obj = hashlib.md5(text.encode())
    hash_int = int(hash_obj.hexdigest(), 16)
    return palette[hash_int % len(palette)]


def generate_hsl_color(hue: float, saturation: float = 0.7, lightness: float = 0.5) -> str:
    """Generate a color using HSL values and convert to hex"""
    rgb = colorsys.hls_to_rgb(hue, lightness, saturation)
    return "#{:02x}{:02x}{:02x}".format(
        int(rgb[0] * 255),
        int(rgb[1] * 255),
        int(rgb[2] * 255)
    )


def extract_timestamp_from_id(node_id: str) -> Optional[int]:
    """Extract timestamp from node ID patterns like 'mem_1756642265634'"""
    # Pattern for extracting timestamps from IDs
    patterns = [
        r'mem_(\d{13})',      # mem_1756642265634 (13 digits - milliseconds)
        r'mem_(\d{10})',      # mem_1756642265 (10 digits - seconds)
        r'_(\d{13})$',        # any_id_1756642265634
        r'_(\d{10})$',        # any_id_1756642265
        r'(\d{13})',          # standalone 13-digit timestamp
        r'(\d{10})'           # standalone 10-digit timestamp
    ]
    
    for pattern in patterns:
        match = re.search(pattern, node_id)
        if match:
            timestamp = int(match.group(1))
            # Convert seconds to milliseconds if needed
            if len(match.group(1)) == 10:
                timestamp *= 1000
            return timestamp
    return None


def timestamp_to_datetime(timestamp: int) -> datetime:
    """Convert timestamp (milliseconds) to datetime"""
    return datetime.fromtimestamp(timestamp / 1000)
def get_time_range_query_clause(time_filter: str, custom_start: Optional[datetime] = None, custom_end: Optional[datetime] = None) -> Tuple[str, str]:
    """Generate Cypher WHERE clause for time filtering - returns (where_clause, additional_match)"""
    if time_filter == "All Time":
        return "", ""
    
    now = datetime.now()
    
    if time_filter == "Last Hour":
        start_time = now - timedelta(hours=1)
        end_time = now
    elif time_filter == "Last 24 Hours":
        start_time = now - timedelta(days=1)
        end_time = now
    elif time_filter == "Last Week":
        start_time = now - timedelta(weeks=1)
        end_time = now
    elif time_filter == "Last Month":
        start_time = now - timedelta(days=30)
        end_time = now
    elif time_filter == "Last 3 Months":
        start_time = now - timedelta(days=90)
        end_time = now
    elif time_filter == "Custom Range":
        if not custom_start or not custom_end:
            return "", ""
        start_time = custom_start
        end_time = custom_end
    else:
        start_time = now - timedelta(days=1)  # Default to last 24 hours
        end_time = now
    
    # Convert to ISO format strings for datetime comparison
    start_iso = start_time.strftime('%Y-%m-%dT%H:%M:%S.%f')
    end_iso = end_time.strftime('%Y-%m-%dT%H:%M:%S.%f')
    
    # Convert to timestamps (milliseconds) for ID extraction
    start_ts = int(start_time.timestamp() * 1000)
    end_ts = int(end_time.timestamp() * 1000)
    
    where_clause = f"""
    WHERE n.id IS NOT NULL AND (
        (n.created_at IS NOT NULL AND 
         n.created_at >= "{start_iso}" AND 
         n.created_at <= "{end_iso}") OR
        (n.created_at IS NULL AND n.id =~ 'mem_(\\d{{13}}).*' AND 
         toInteger(substring(n.id, 4, 13)) >= {start_ts} AND 
         toInteger(substring(n.id, 4, 13)) <= {end_ts}) OR
        (n.created_at IS NULL AND n.id =~ 'mem_(\\d{{10}}).*' AND 
         toInteger(substring(n.id, 4, 10)) * 1000 >= {start_ts} AND 
         toInteger(substring(n.id, 4, 10)) * 1000 <= {end_ts})
    )"""
    return where_clause, ""

def get_label_color(labels: List[str], color_scheme: str = "pastel") -> str:
    """Get color for node based on its labels using selected color scheme"""
    if not labels:
        return "#9E9E9E"  # Gray for unlabeled nodes
    
    # Use the first label for color determination that isnt "Entity"
    primary_label = labels 
    print(primary_label)
    if color_scheme == "material":
        return generate_color_from_string(primary_label, MATERIAL_PALETTE)
    elif color_scheme == "pastel":
        return generate_color_from_string(primary_label, PASTEL_PALETTE)
    elif color_scheme == "vibrant":
        return generate_color_from_string(primary_label, VIBRANT_PALETTE)
    elif color_scheme == "hsl":
        # Generate HSL color based on label hash
        hash_val = hash(primary_label) % 360
        return generate_hsl_color(hash_val / 360.0)
    else:
        # Fallback to original color mapping
        color_map = {
            "File": "#2196F3",
            "Project": "#FF9800", 
            "Thought": "#9C27B0",
            "Document": "#4CAF50",
            "Codebase": "#F44336",
            "Query": "#00BCD4",
            "Plan": "#FFEB3B",
            "Step": "#E91E63",
            "Response": "#8BC34A",
            "Session": "#795548",
            "Command": "#CC4444"
        }
        return color_map.get(primary_label, "#9E9E9E")


def serialize(value):
    """Turn Neo4j Node/Relationship into dicts, leave others unchanged"""
    if isinstance(value, Node):
        return {
            "id": value.element_id,
            "labels": list(value.labels),
            "properties": dict(value.items()),
        }
    elif isinstance(value, Relationship):
        return {
            "id": value.element_id,
            "type": value.type,
            "start": value.start_node.element_id,
            "end": value.end_node.element_id,
            "properties": dict(value.items()),
        }
    elif isinstance(value, tuple):
        return list(value)
    else:
        return value


@dataclass
class NodeData:
    """Represents a Neo4j node with all its properties"""
    id: str
    labels: List[str]
    properties: Dict[str, Any]
    
    @property
    def display_name(self) -> str:
        """Get display name for the node"""
        props = self.properties
        return (props.get("name") or 
                props.get("text", "")[:50] or 
                props.get("id") or 
                f"Node {self.id}")
    
    @property
    def color(self) -> str:
        """Get color based on node labels"""
        color_map = {
            "File": "blue",
            "Project": "orange", 
            "Thought": "purple",
            "Document": "green",
            "Codebase": "red",
            "Query": "cyan",
            "Plan": "yellow",
            "Step": "pink",
            "Response": "lime",
            "Session": "brown"
        }
        for label in self.labels:
            if label in color_map:
                return color_map[label]
        return "gray"
    
    @property
    def timestamp(self) -> Optional[datetime]:
        """Extract timestamp from node ID if available"""
        node_id = self.properties.get("id", "")
        ts = extract_timestamp_from_id(node_id)
        return timestamp_to_datetime(ts) if ts else None


class VectorClient:
    """Wrapper for ChromaDB operations"""
    
    def __init__(self, persist_dir: str, embedding_model: str = "all-MiniLM-L6-v2"):
        os.makedirs(persist_dir, exist_ok=True)
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )
        
    def get_by_metadata(self, collection: str, where: dict, limit: int = 5):
        col = self.get_collection(collection)
        return col.get(where=where, limit=limit)

    def get_collection(self, name: str):
        return self._client.get_or_create_collection(
            name=name, 
            embedding_function=self._ef
        )

    def add_texts(self, collection: str, ids, texts, metadatas=None):
        col = self.get_collection(collection)
        col.add(ids=ids, documents=texts, metadatas=metadatas)

    def query(self, collection: str, text: str, n_results: int = 5, where=None):
        col = self.get_collection(collection)
        kwargs = {"query_texts": [text], "n_results": n_results}
        if where:
            kwargs["where"] = where
        return col.query(**kwargs)


def get_node_subgraph(driver, node_id, max_depth=2):
    """Get the complete subgraph for a selected node"""
    cypher_query = f"""
    MATCH (selected)
    WHERE selected.id = '{node_id}'
    CALL {{
        WITH selected
        MATCH (selected)-[r*1..{max_depth}]-(connected)
        RETURN selected as n, null as r, connected as m
        UNION ALL
        WITH selected
        MATCH (selected)-[r]-(connected)
        RETURN selected as n, r, connected as m
        UNION ALL
        WITH selected
        MATCH (connected)-[r]-(selected)
        RETURN connected as n, r, selected as m
    }}
    RETURN DISTINCT n, r, m
    """
    
    with driver.session() as session:
        result = session.run(cypher_query)
        rows = []
        for record in result:
            serialized = {k: serialize(v) for k, v in record.items() if v is not None}
            rows.append(serialized)
    
    return rows

def display_node_details(node_data, vector_client):
    """Display node details in sidebar"""
    if not node_data:
        return
    
    st.sidebar.success("Node Selected!")
    st.sidebar.subheader("📍 Node Details")
    st.sidebar.write(f"**ID:** `{node_data['id']}`")
    st.sidebar.write(f"**Labels:** {', '.join(node_data['labels'])}")
    st.sidebar.write(f"**Display Name:** {node_data['display_name']}")
    
    if node_data.get('is_subgraph'):
        st.sidebar.info("📡 This node was added from subgraph expansion")
    
    # Show timestamp if available
    if "id" in node_data['properties']:
        ts = extract_timestamp_from_id(node_data['properties']['id'])
        if ts:
            dt = timestamp_to_datetime(ts)
            st.sidebar.write(f"**Timestamp:** {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            st.sidebar.write(f"**Time Ago:** {format_time_ago(dt)}")
    
    # Properties
    st.sidebar.subheader("Properties")
    if node_data['properties']:
        st.sidebar.json(node_data['properties'])
    else:
        st.sidebar.write("No properties found")
    
    # Related content from Chroma
    st.sidebar.subheader("🔗 Related Content")
    try:
        if "File" in node_data['labels']:
            file_id = node_data['properties'].get("id")
            if file_id:
                chroma_res = vector_client.get_by_metadata(
                    collection="long_term_docs",
                    where={"file_id": file_id},
                    limit=3
                )
                if chroma_res and 'documents' in chroma_res:
                    for i, doc in enumerate(chroma_res['documents'][:3]):
                        with st.sidebar.expander(f"Chunk {i+1}", expanded=False):
                            st.write(doc[:500] + "..." if len(doc) > 500 else doc)
                else:
                    st.sidebar.write("No chunks found for this file")
            else:
                st.sidebar.warning("File node missing ID property")
        else:
            chroma_res = vector_client.query(
                collection="long_term_docs",
                text=node_data['display_name'],
                n_results=3
            )
            if chroma_res and 'documents' in chroma_res:
                for i, doc in enumerate(chroma_res['documents'][0][:3]):
                    with st.sidebar.expander(f"Match {i+1}", expanded=False):
                        st.write(doc[:300] + "..." if len(doc) > 300 else doc)
            else:
                st.sidebar.write("No related content found")
                
    except Exception as e:
        st.sidebar.error(f"Error fetching related content: {e}")


def format_time_ago(dt: datetime) -> str:
    """Format datetime as 'time ago' string"""
    now = datetime.now()
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days} days ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hours ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minutes ago"
    else:
        return "Just now"

def calculate_temporal_positions(rows, subgraph_data=None, layout_type="temporal_horizontal"):
    """Calculate node positions based on timestamps and layout type"""
    all_rows = rows + (subgraph_data if subgraph_data else [])
    
    # Extract all nodes with timestamps
    nodes_with_time = {}
    nodes_without_time = []
    
    for row in all_rows:
        for key, val in row.items():
            if isinstance(val, dict) and "id" in val and "labels" in val:
                node_id = val["id"]
                props = val.get("properties", {})
                
                # Extract timestamp
                ts = None
                if "id" in props:
                    ts = extract_timestamp_from_id(props["id"])
                
                if ts:
                    nodes_with_time[node_id] = {
                        "timestamp": ts,
                        "datetime": timestamp_to_datetime(ts),
                        "data": val
                    }
                else:
                    nodes_without_time.append({"id": node_id, "data": val})
    
    positions = {}
    
    if layout_type == "temporal_horizontal":
        positions = calculate_temporal_horizontal_layout(nodes_with_time, nodes_without_time)
    elif layout_type == "temporal_vertical":
        positions = calculate_temporal_vertical_layout(nodes_with_time, nodes_without_time)
    elif layout_type == "hierarchical_time":
        positions = calculate_hierarchical_time_layout(nodes_with_time, nodes_without_time, all_rows)
    elif layout_type == "circular_time":
        positions = calculate_circular_time_layout(nodes_with_time, nodes_without_time)
    elif layout_type == "force_time_weighted":
        positions = calculate_force_time_weighted_layout(nodes_with_time, nodes_without_time)
    else:
        # Default: no fixed positions, let pyvis handle it
        positions = {}
    
    return positions


def calculate_temporal_horizontal_layout(nodes_with_time, nodes_without_time):
    """Oldest on left, newest on right, flowing top to bottom"""
    positions = {}
    
    if not nodes_with_time:
        return positions
    
    # Sort by timestamp
    sorted_nodes = sorted(nodes_with_time.items(), key=lambda x: x[1]["timestamp"])
    
    # Calculate time span
    min_time = sorted_nodes[0][1]["timestamp"]
    max_time = sorted_nodes[-1][1]["timestamp"]
    time_span = max_time - min_time if max_time > min_time else 1
    
    # Layout parameters
    width = 2000  # Total width
    height = 1500  # Total height
    layers_per_time_unit = 5  # How many vertical layers per time period
    
    # Group nodes by time buckets for vertical stacking
    time_buckets = defaultdict(list)
    bucket_size = max(1, time_span // 20)  # 20 time buckets
    
    for node_id, node_info in sorted_nodes:
        bucket = int((node_info["timestamp"] - min_time) // bucket_size)
        time_buckets[bucket].append((node_id, node_info))
    
    # Position nodes
    for bucket_idx, nodes in time_buckets.items():
        x = int((bucket_idx / len(time_buckets)) * width)
        
        # Stack nodes vertically within each time bucket
        for i, (node_id, node_info) in enumerate(nodes):
            y = int((i % layers_per_time_unit) * (height / layers_per_time_unit))
            positions[node_id] = {"x": x, "y": y}
    
    # Position nodes without timestamps on the far right
    for i, node_info in enumerate(nodes_without_time):
        positions[node_info["id"]] = {
            "x": width + 200,
            "y": int((i % 10) * (height / 10))
        }
    
    return positions


def calculate_temporal_vertical_layout(nodes_with_time, nodes_without_time):
    """Oldest at top, newest at bottom, flowing left to right"""
    positions = {}
    
    if not nodes_with_time:
        return positions
    
    # Sort by timestamp
    sorted_nodes = sorted(nodes_with_time.items(), key=lambda x: x[1]["timestamp"])
    
    # Calculate time span
    min_time = sorted_nodes[0][1]["timestamp"]
    max_time = sorted_nodes[-1][1]["timestamp"]
    time_span = max_time - min_time if max_time > min_time else 1
    
    # Layout parameters
    width = 2000
    height = 1500
    layers_per_time_unit = 5
    
    # Group nodes by time buckets for horizontal stacking
    time_buckets = defaultdict(list)
    bucket_size = max(1, time_span // 15)  # 15 time buckets
    
    for node_id, node_info in sorted_nodes:
        bucket = int((node_info["timestamp"] - min_time) // bucket_size)
        time_buckets[bucket].append((node_id, node_info))
    
    # Position nodes
    for bucket_idx, nodes in time_buckets.items():
        y = int((bucket_idx / len(time_buckets)) * height)
        
        # Stack nodes horizontally within each time bucket
        for i, (node_id, node_info) in enumerate(nodes):
            x = int((i % layers_per_time_unit) * (width / layers_per_time_unit))
            positions[node_id] = {"x": x, "y": y}
    
    # Position nodes without timestamps at the bottom
    for i, node_info in enumerate(nodes_without_time):
        positions[node_info["id"]] = {
            "x": int((i % 10) * (width / 10)),
            "y": height + 200
        }
    
    return positions


def calculate_hierarchical_time_layout(nodes_with_time, nodes_without_time, all_rows):
    """Hierarchical layout with time-based levels"""
    positions = {}
    
    if not nodes_with_time:
        return positions
    
    # Build relationship graph to understand hierarchy
    relationships = defaultdict(set)
    for row in all_rows:
        if "r" in row and row["r"] and "n" in row and "m" in row:
            src = row["n"].get("id") if row["n"] else None
            dst = row["m"].get("id") if row["m"] else None
            if src and dst:
                relationships[src].add(dst)
    
    # Sort by timestamp and create time-based levels
    sorted_nodes = sorted(nodes_with_time.items(), key=lambda x: x[1]["timestamp"])
    
    # Create time-based levels
    levels = []
    current_level = []
    level_time_threshold = 3600000  # 1 hour in milliseconds
    
    current_time = sorted_nodes[0][1]["timestamp"]
    
    for node_id, node_info in sorted_nodes:
        if node_info["timestamp"] - current_time > level_time_threshold:
            if current_level:
                levels.append(current_level)
                current_level = []
            current_time = node_info["timestamp"]
        current_level.append((node_id, node_info))
    
    if current_level:
        levels.append(current_level)
    
    # Position nodes in hierarchical levels
    width = 2000
    height = 1500
    level_height = height / len(levels) if levels else height
    
    for level_idx, level_nodes in enumerate(levels):
        y = int(level_idx * level_height)
        node_width = width / len(level_nodes) if level_nodes else width
        
        for i, (node_id, node_info) in enumerate(level_nodes):
            x = int(i * node_width + node_width / 2)
            positions[node_id] = {"x": x, "y": y}
    
    # Position nodes without timestamps at bottom
    if nodes_without_time:
        for i, node_info in enumerate(nodes_without_time):
            positions[node_info["id"]] = {
                "x": int((i % 10) * (width / 10)),
                "y": height + 100
            }
    
    return positions


def calculate_circular_time_layout(nodes_with_time, nodes_without_time):
    """Circular layout ordered by time"""
    positions = {}
    
    if not nodes_with_time:
        return positions
    
    sorted_nodes = sorted(nodes_with_time.items(), key=lambda x: x[1]["timestamp"])
    
    # Circular layout parameters
    center_x, center_y = 1000, 750
    radius = 600
    
    # Position nodes in a circle ordered by time
    for i, (node_id, node_info) in enumerate(sorted_nodes):
        angle = (2 * math.pi * i) / len(sorted_nodes)
        x = int(center_x + radius * math.cos(angle))
        y = int(center_y + radius * math.sin(angle))
        positions[node_id] = {"x": x, "y": y}
    
    # Position nodes without timestamps in inner circle
    inner_radius = 300
    for i, node_info in enumerate(nodes_without_time):
        angle = (2 * math.pi * i) / max(len(nodes_without_time), 1)
        x = int(center_x + inner_radius * math.cos(angle))
        y = int(center_y + inner_radius * math.sin(angle))
        positions[node_info["id"]] = {"x": x, "y": y}
    
    return positions


def calculate_force_time_weighted_layout(nodes_with_time, nodes_without_time):
    """Force-directed layout with time-based weights"""
    positions = {}
    
    if not nodes_with_time:
        return positions
    
    # For this layout, we'll provide initial positions based on time
    # and let the force-directed algorithm adjust from there
    sorted_nodes = sorted(nodes_with_time.items(), key=lambda x: x[1]["timestamp"])
    
    # Initial positioning in a time-based grid
    grid_width = int(math.sqrt(len(sorted_nodes))) + 1
    cell_size = 100
    
    for i, (node_id, node_info) in enumerate(sorted_nodes):
        row = i // grid_width
        col = i % grid_width
        
        # Add time-based offset to create temporal clusters
        time_offset = (node_info["timestamp"] % 10000) / 100
        
        positions[node_id] = {
            "x": int(col * cell_size + time_offset),
            "y": int(row * cell_size)
        }
    
    # Position nodes without timestamps randomly but clustered
    for i, node_info in enumerate(nodes_without_time):
        positions[node_info["id"]] = {
            "x": int((len(sorted_nodes) % grid_width) * cell_size + (i % 5) * 50),
            "y": int((len(sorted_nodes) // grid_width + 1) * cell_size + (i // 5) * 50)
        }
    
    return positions


def fetch_vector_content_for_nodes(nodes_data, vector_client):
    """Pre-fetch vector store content for all nodes"""
    vector_data = {}
    
    for node_id, node_info in nodes_data.items():
        try:
            content_items = []
            
            # Check if this is a File node with direct collection mapping
            if "File" in node_info['labels']:
                file_id = node_info['properties'].get("id")
                if file_id:
                    # Try to get content from collection with matching name
                    try:
                        chroma_res = vector_client.get_by_metadata(
                            collection="long_term_docs",
                            where={"file_id": file_id},
                            limit=3
                        )
                        if chroma_res and 'documents' in chroma_res and chroma_res['documents']:
                            for doc in chroma_res['documents'][:3]:
                                content_items.append({
                                    "type": "file_chunk",
                                    "content": doc[:500] + ("..." if len(doc) > 500 else "")
                                })
                    except:
                        pass
            
            # If node ID matches a collection name, try to get content from that collection
            node_prop_id = node_info['properties'].get("id", "")
            if node_prop_id:
                try:
                    # Try using the node's property ID as a collection name
                    col = vector_client.get_collection(node_prop_id)
                    sample = col.get(limit=3, include=["documents", "metadatas"])
                    if sample and sample.get("ids"):
                        for i, doc_id in enumerate(sample["ids"][:3]):
                            doc = sample["documents"][i] if sample.get("documents") and len(sample["documents"]) > i else ""
                            if doc:
                                content_items.append({
                                    "type": "collection_doc",
                                    "id": doc_id,
                                    "content": doc[:500] + ("..." if len(doc) > 500 else ""),
                                    "metadata": sample["metadatas"][i] if sample.get("metadatas") and len(sample["metadatas"]) > i else {}
                                })
                except:
                    pass
            
            # Fallback: semantic search using display name
            if not content_items:
                try:
                    chroma_res = vector_client.query(
                        collection="long_term_docs",
                        text=node_info['display_name'],
                        n_results=2
                    )
                    if chroma_res and 'documents' in chroma_res and chroma_res['documents']:
                        for doc in chroma_res['documents'][0][:2]:
                            content_items.append({
                                "type": "semantic_match",
                                "content": doc[:300] + ("..." if len(doc) > 300 else "")
                            })
                except:
                    pass
            
            if content_items:
                vector_data[node_id] = content_items
                
        except Exception as e:
            # Silently skip nodes that cause errors
            continue
    
    return vector_data

def safe_serialize(v):
    try:
        return json.loads(safe_json_dumps(v))
    except Exception:
        return str(v)


def safe_json_dumps(obj):
    def default(o):
        # Handle Python datetime/date
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        # Handle Neo4j DateTime (if using neo4j driver objects)
        if hasattr(o, "to_native"):
            return o.to_native().isoformat()
        # Fallback to string
        return str(o)
    return json.dumps(obj, default=default, ensure_ascii=False, indent=2)

def sanitize_for_pyvis(data):
    if isinstance(data, (datetime, date)):
        return data.isoformat()
    if hasattr(data, "to_native"):  # Neo4j DateTime
        return data.to_native().isoformat()
    if isinstance(data, dict):
        return {k: sanitize_for_pyvis(v) for k, v in data.items()}
    if isinstance(data, list):
        return [sanitize_for_pyvis(v) for v in data]
    return data


def create_enhanced_graph_html(net, vector_data, output_path="enhanced_graph.html"):
    """
    Enhanced Pyvis HTML with addon injection

    """
    # Save base Pyvis graph to temp file
    temp_file = "temp_pyvis_graph.html"
    net.save_graph(temp_file)
    
    # Read the Pyvis HTML
    with open(temp_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Read the addon HTML (from the artifact)
    addon_file = "./Memory/dashboard/graphui.html"  # Save the artifact as this file
    with open(addon_file, 'r', encoding='utf-8') as f:
        addon_html = f.read()
    
    # Convert vector_data to JSON string
    vector_json = safe_json_dumps(vector_data)
    
    # Inject vector data into the addon's initialization
    addon_with_data = addon_html.replace(
        "GraphAddon.init({})",
        f"GraphAddon.init({vector_json})"
    )
    
    # Inject addon before closing body tag
    enhanced_html = html_content.replace(
        "</body>",
        addon_with_data + "\n</body>"
    )
    
    return enhanced_html

def create_graph_visualization(rows, selected_node=None, subgraph_data=None,
                               color_scheme="pastel", layout_type="default", max_nodes=5000):
    """Build a pyvis.Network with improved handling for dense networks.

    - rows: list of serialized rows from Neo4j query
    - returns: (net, nodes_data)
    """
    net = Network(height="900px", width="100%", notebook=False, directed=True, bgcolor="#0f1419", font_color="white")

    # set an upper cap on nodes to avoid freezing the browser
    node_count = 0

    # compute connection counts
    connection_counts = defaultdict(int)
    for row in rows:
        if "r" in row and row["r"]:
            src = row.get("m", {}).get("id")
            dst = row.get("n", {}).get("id")
            if src:
                connection_counts[src] += 1
            if dst:
                connection_counts[dst] += 1

    # optionally compute positions for temporal layouts
    positions = {}
    if layout_type != "default":
        try:
            positions = calculate_temporal_positions(rows, subgraph_data, layout_type)
        except Exception:
            positions = {}

    added_nodes = set()
    nodes_data = {}

    # Add nodes with dynamic sizing by degree and color scaling
    for row in rows:
        for key, val in row.items():
            if isinstance(val, dict) and "id" in val and "labels" in val:
                node_id = val["id"]
                if node_id in added_nodes:
                    continue

                # respect max nodes limit
                node_count += 1
                if node_count > max_nodes:
                    # stop adding more nodes to the visualization
                    continue

                props = val.get("properties", {})
                node_name = props.get("name") or props.get("title") or (props.get("text")[:40] if props.get("text") else "") or f"Node {node_id}"
                labels_list = [label for label in (props.get("labels") or val.get("labels")) if label != "Entity"]
                # print(labels_list)
                # color by first label
                if labels_list:
                    color = get_label_color(labels_list[0], color_scheme)
                else:
                    color = "#9E9E9E"
                
                deg = connection_counts.get(node_id, 0)
                # size scale: base 14, + growth with sqrt of degree
                node_size = 14 + int((deg ** 0.5) * 4)

                # make hubs heavier mass to push others away in physics
                mass = 1 + (deg / 10.0)

                node_options = {
                    "borderWidth": 1 if selected_node != node_id else 4,
                    "size": node_size,
                    "mass": mass,
                    "font": {"size": 12}
                }

                if node_id in positions:
                    node_options["x"] = positions[node_id]["x"]
                    node_options["y"] = positions[node_id]["y"]
                    node_options["physics"] = False

                title = {
                    "properties": props,
                    "labels": labels_list
                }
                # include timestamp briefly in title if available
                try:
                    ts = extract_timestamp_from_id(props.get("id")) if props.get("id") else None
                    if ts:
                        dt = timestamp_to_datetime(ts)
                        title = f"{title}\n⏰ {dt.strftime('%Y-%m-%d %H:%M:%S')}"
                except Exception:
                    pass

                # Use label minimally (short) to avoid overlap; full details in panel
                short_label = (node_name[:28] + '...') if len(node_name) > 28 else node_name

                clean_props = sanitize_for_pyvis(props)
                title_data = {
                    "properties": clean_props,
                    "labels": labels_list
                }
                net.add_node(node_id, label=short_label, title=safe_json_dumps(title_data), color=color, **node_options)
                
                added_nodes.add(node_id)

                nodes_data[node_id] = {
                    "id": node_id,
                    "labels": labels_list,
                    "properties": props,
                    "display_name": node_name
                }

    # Add relationships; use title (tooltip) instead of label to reduce clutter
    for row in rows:
        if "r" in row and row["r"] and "id" in row.get("n", {}) and "id" in row.get("m", {}):
            src = row["m"]["id"]
            dst = row["n"]["id"]
            if src not in added_nodes or dst not in added_nodes:
                continue
            rel_data = row["r"]
            rel_type = rel_data.get("properties", {}).get("rel") or rel_data.get("type") or "REL"

            # adjust length by connectivity to reduce local collapse
            avg_conn = (connection_counts.get(src, 0) + connection_counts.get(dst, 0)) / 2
            if avg_conn > 12:
                length = 350
            elif avg_conn > 6:
                length = 280
            else:
                length = 200

            # use title for hover tooltip and leave label blank
            net.add_edge(src, dst, title=rel_type, label="", length=length)

    # Subgraph edges (if provided)
    if subgraph_data:
        for row in subgraph_data:
            if "r" in row and row["r"] and "id" in row.get("n", {}) and "id" in row.get("m", {}):
                src = row["n"]["id"]
                dst = row["m"]["id"]
                if src in added_nodes and dst in added_nodes:
                    net.add_edge(src, dst, title=rel.get("type", "REL"), label="", length=200, color={"color": "#999"})

    # set some python options (pyvis wrapper -> vis.js)
    net.set_options('''
    var options = {
      "interaction": { "hover": true, "navigationButtons": true, "zoomView": true },
      "edges": { "smooth": { "enabled": true, "type": "dynamic" }, "arrows": { "to": { "enabled": true } } },
      "layout": {
        "improvedLayout": false
      },
      "physics": {
        "enabled": true,
        "stabilization": { "enabled": true, "iterations": 300 },
        "barnesHut": { "gravitationalConstant": -9000, "centralGravity": 0.06, "springLength": 300, "springConstant": 0.01, "damping": 0.62 }
      }
    }
    ''')

    return net, nodes_data

def execute_query_and_display(driver, vector_client, cypher_query, color_scheme="pastel",
                              layout_type="default", max_nodes=5000):
    """Execute query and display results with layout options"""
    with driver.session() as session:
        result = session.run(cypher_query)
        rows = []
        for record in result:
            serialized = {k: serialize(v) for k, v in record.items()}
            rows.append(serialized)

    if not rows:
        st.warning("No results found")
        return

    # Store data in session state
    st.session_state.query_results = rows

    # Get selected node and fetch subgraph if needed
    selected_node_id = st.session_state.get('selected_node_id', "")
    subgraph_data = None

    if selected_node_id and st.session_state.get('show_subgraph', False):
        try:
            # Try to get property ID first
            property_id = None
            for row in rows:
                for key, val in row.items():
                    if isinstance(val, dict) and val.get("id") == selected_node_id:
                        property_id = val.get("properties", {}).get("id")
                        break
                if property_id:
                    break

            if property_id:
                subgraph_data = get_node_subgraph(driver, property_id)
                if subgraph_data:
                    st.info(f"🔍 Showing subgraph for selected node. Found {len(subgraph_data)} additional connections.")

        except Exception as e:
            st.warning(f"Could not fetch subgraph: {e}")

    # Create and display graph with layout
    net, nodes_data = create_graph_visualization(
        rows,
        selected_node=selected_node_id,
        subgraph_data=subgraph_data,
        color_scheme=color_scheme,
        layout_type=layout_type,
        max_nodes=max_nodes
    )
    st.session_state.nodes_data = nodes_data

    # Create interactive HTML
    interactive_html = create_enhanced_graph_html(net, nodes_data, vector_client)

    # Display layout info
    if layout_type != "default":
        layout_names = {
            "temporal_horizontal": "Temporal Horizontal (Oldest ← → Newest)",
            "temporal_vertical": "Temporal Vertical (Oldest ↑ ↓ Newest)",
            "hierarchical_time": "Hierarchical Time Levels",
            "circular_time": "Circular Time Ordered",
            "force_time_weighted": "Force-Directed with Time Weights"
        }
        st.info(f"Layout: {layout_names.get(layout_type, layout_type)}")

    # Display with custom HTML that includes click handling
    components.html(interactive_html, height=900)

    # Show time distribution if timestamps are found
    all_rows = rows + (subgraph_data if subgraph_data else [])
    show_time_distribution(all_rows)

    # Node selection and controls
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.markdown("💡 **Click nodes in the graph above to select them**, or use the sidebar controls")

    with col2:
        if st.button("Refresh Graph"):
            st.rerun()

    with col3:
        if st.button("🧹 Clear Selection") and selected_node_id:
            st.session_state.selected_node_id = ""
            st.session_state.show_subgraph = False
            st.rerun()

    # Display selection info
    if selected_node_id and selected_node_id in nodes_data:
        node_info = nodes_data[selected_node_id]
        st.info(f"Selected: **{node_info['display_name']}** ({', '.join(node_info['labels'])})")

    # Create table view
    st.subheader("Data Table")
    create_data_table(all_rows, subgraph_data is not None)

def create_data_table(all_data, has_subgraph=False):
    """Create data table with timestamp info"""
    cleaned = []
    for row in all_data:
        entry = {}
        if "n" in row and isinstance(row["n"], dict):
            entry["n_id"] = row["n"].get("id")
            entry["n_labels"] = ', '.join(row["n"].get("labels", []))
            entry["n_props"] = str(row["n"].get("properties", {}))
            
            # Add timestamp info
            if "properties" in row["n"] and "id" in row["n"]["properties"]:
                ts = extract_timestamp_from_id(row["n"]["properties"]["id"])
                if ts:
                    dt = timestamp_to_datetime(ts)
                    entry["n_timestamp"] = dt.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    entry["n_timestamp"] = "N/A"
            else:
                entry["n_timestamp"] = "N/A"
                
        if "m" in row and isinstance(row["m"], dict):
            entry["m_id"] = row["m"].get("id")
            entry["m_labels"] = ', '.join(row["m"].get("labels", []))
            entry["m_props"] = str(row["m"].get("properties", {}))
            
            # Add timestamp info
            if "properties" in row["m"] and "id" in row["m"]["properties"]:
                ts = extract_timestamp_from_id(row["m"]["properties"]["id"])
                if ts:
                    dt = timestamp_to_datetime(ts)
                    entry["m_timestamp"] = dt.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    entry["m_timestamp"] = "N/A"
            else:
                entry["m_timestamp"] = "N/A"
                
        if "r" in row and isinstance(row["r"], dict):
            entry["r_type"] = row["r"].get("type")
            entry["r_props"] = str(row["r"].get("properties", {}))
        cleaned.append(entry)

    df = pd.DataFrame(cleaned)
    
    if has_subgraph:
        st.caption("Table includes both original query results and expanded subgraph data")
    
    st.dataframe(df, use_container_width=True)


def show_time_distribution(rows):
    """Show time distribution of nodes, excluding future timestamps"""
    timestamps = []
    
    now = datetime.now()
    for row in rows:
        for key, val in row.items():
            if isinstance(val, dict) and "properties" in val and "id" in val["properties"]:
                ts = extract_timestamp_from_id(val["properties"]["id"])
                if ts:
                    dt = timestamp_to_datetime(ts)
                    if dt <= now:  # Exclude future timestamps
                        timestamps.append(dt)
    
    if timestamps:
        st.subheader("Time Distribution")
        timestamps_df = pd.DataFrame({"timestamp": timestamps})
        timestamps_df["date"] = timestamps_df["timestamp"].dt.date
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Nodes with Timestamps", len(timestamps))
            if timestamps:
                st.metric("Date Range", f"{min(timestamps).date()} to {max(timestamps).date()}")
        
        with col2:
            # Group by date
            daily_counts = timestamps_df.groupby("date").size().reset_index(name="count")
            st.bar_chart(daily_counts.set_index("date"))

def browse_chroma_store(vector_client):
    """Browse and search Chroma vector store collections"""
    st.subheader("Chroma Vector Store Browser")

    try:
        # Get available collections
        collections = vector_client._client.list_collections()
        collection_names = [c.name for c in collections]

        if not collection_names:
            st.warning("No collections found in Chroma store")
            return

        st.info(f"Found {len(collection_names)} collections")

        # Tabs for browsing/searching
        tab0, tab1, tab2 = st.tabs(["📚 All Collections", "📂 Browse Collection", "🔍 Semantic Search"])

        # --- Tab 0: Overview of all collections ---
        with tab0:
            st.subheader("All Collections Overview")
            for cname in collection_names:
                col = vector_client.get_collection(cname)
                count = col.count()
                with st.expander(f"📁 {cname} ({count} items)"):
                    st.write(f"**Collection name:** {cname}")
                    st.write(f"**Items:** {count}")
                    if count > 0:
                        try:
                            # Get a small sample
                            sample = col.get(limit=min(5, count), include=["documents", "metadatas"])
                            if sample and sample.get("ids"):
                                for i in range(len(sample["ids"])):
                                    st.caption(f"ID: `{sample['ids'][i]}`")
                                    if sample.get("documents") and len(sample["documents"]) > i:
                                        doc_text = sample["documents"][i]
                                        st.text(doc_text[:300] + ("..." if len(doc_text) > 300 else ""))
                                    if sample.get("metadatas") and sample["metadatas"] and len(sample["metadatas"]) > i and sample["metadatas"][i]:
                                        st.json(sample["metadatas"][i])
                            else:
                                st.write("No sample data available")
                        except Exception as e:
                            st.error(f"Error getting sample data: {e}")

        # --- Tab 1: Browse inside a single collection ---
        with tab1:
            selected_collection = st.selectbox("Select Collection to Browse", collection_names, key="browse_select")
            collection = vector_client.get_collection(selected_collection)
            item_count = collection.count()
            st.success(f"**Collection:** `{selected_collection}` | **Items:** {item_count}")

            if item_count == 0:
                st.warning("This collection is empty")
            else:
                # Pagination
                col1, col2 = st.columns(2)
                with col1:
                    page_size = st.slider("Items per page", 5, 100, 20, key="browse_page_size")
                with col2:
                    num_pages = max(1, (item_count + page_size - 1) // page_size)
                    page = st.number_input("Page", 1, num_pages, 1, key="browse_page")

                offset = (page - 1) * page_size
                try:
                    items = collection.get(limit=page_size, offset=offset, include=["documents", "metadatas"])
                    if not items or not items.get("ids"):
                        st.warning("No documents found in this page")
                    else:
                        st.write(f"Showing items {offset+1} to {min(offset+page_size, item_count)} of {item_count}")
                        for i in range(len(items["ids"])):
                            doc_id = items["ids"][i]
                            doc = items["documents"][i] if items.get("documents") and len(items["documents"]) > i else "No document content"
                            meta = items["metadatas"][i] if items.get("metadatas") and items["metadatas"] and len(items["metadatas"]) > i else {}
                            with st.expander(f"Document {offset+i+1}: {doc_id}"):
                                st.caption(f"**ID:** `{doc_id}`")
                                if meta:
                                    st.json(meta)
                                st.text_area("Content", value=doc, height=200, key=f"doc_{doc_id}_{i}_{page}")
                except Exception as e:
                    st.error(f"Error browsing collection: {e}")

        # --- Tab 2: Search across one or all collections ---
        with tab2:
            st.subheader("Semantic Search")

            search_scope = st.radio("Search in:", ["All Collections"] + collection_names, horizontal=True, key="search_scope")
            query_text = st.text_area("Search query", placeholder="Enter text to search...", height=100, key="search_query")

            n_results = st.slider("Number of results per collection", 1, 50, 5, key="n_results")

            # Optional metadata filter
            where_filter = {}
            filter_key = st.text_input("Filter key", key="filter_key")
            filter_value = st.text_input("Filter value", key="filter_value")
            if filter_key and filter_value:
                try:
                    try:
                        value = int(filter_value)
                    except:
                        try:
                            value = float(filter_value)
                        except:
                            value = filter_value
                    where_filter = {filter_key: value}
                except Exception as e:
                    st.error(f"Invalid filter: {e}")

            if st.button("🔎 Run Search", use_container_width=True):
                if not query_text.strip():
                    st.warning("Please enter a search query")
                    st.stop()

                with st.spinner("Searching..."):
                    results = []
                    target_collections = collection_names if search_scope == "All Collections" else [search_scope]
                    searched_collections = 0
                    skipped_collections = 0

                    for cname in target_collections:
                        try:
                            col = vector_client.get_collection(cname)
                            
                            # Check if collection has any data before querying
                            count = col.count()
                            if count == 0:
                                skipped_collections += 1
                                continue
                            
                            res = col.query(
                                query_texts=[query_text],
                                n_results=min(n_results, count),  # Don't request more than available
                                where=where_filter if where_filter else None,
                                include=["documents", "distances", "metadatas"]
                            )
                            
                            searched_collections += 1
                            
                            # Debug: Print the structure of res to understand what we're getting
                            # st.write(f"Debug - Collection {cname} result structure:", res.keys() if res else "None")
                            
                            if res and res.get("ids") and res["ids"][0]:
                                for i in range(len(res["ids"][0])):
                                    # Handle both "distance" and "distances" field names
                                    distance = None
                                    if res.get("distances") and len(res["distances"]) > 0 and len(res["distances"][0]) > i:
                                        distance = res["distances"][0][i]
                                    elif res.get("distance") and len(res["distance"]) > 0 and len(res["distance"][0]) > i:
                                        distance = res["distance"][0][i]
                                    else:
                                        distance = 0.0  # Default if no distance found
                                    
                                    document = ""
                                    if res.get("documents") and len(res["documents"]) > 0 and len(res["documents"][0]) > i:
                                        document = res["documents"][0][i]
                                    
                                    metadata = {}
                                    if (res.get("metadatas") and len(res["metadatas"]) > 0 and 
                                        res["metadatas"][0] and len(res["metadatas"][0]) > i):
                                        metadata = res["metadatas"][0][i] or {}
                                    
                                    results.append({
                                        "collection": cname,
                                        "id": res["ids"][0][i],
                                        "distance": distance,
                                        "document": document,
                                        "metadata": metadata
                                    })
                        except Exception as e:
                            error_msg = str(e).lower()
                            if "nothing found on disk" in error_msg or "hnsw segment reader" in error_msg:
                                # Silently skip collections with corrupted/empty indexes
                                skipped_collections += 1
                                continue
                            elif "no query results" in error_msg:
                                # Silently skip collections with no results
                                skipped_collections += 1
                                continue
                            else:
                                # Only show unexpected errors
                                st.error(f"Error searching collection {cname}: {e}")
                                skipped_collections += 1
                            continue

                    if not results:
                        if skipped_collections > 0:
                            st.warning(f"No results found. {skipped_collections} of {len(target_collections)} collections were skipped (empty or inaccessible).")
                        else:
                            st.warning("No results found")
                    else:
                        # Sort globally by distance (lower is better)
                        results = sorted(results, key=lambda x: x["distance"])
                        success_msg = f"Found {len(results)} results across {searched_collections} collections"
                        if skipped_collections > 0:
                            success_msg += f" ({skipped_collections} collections skipped)"
                        st.success(success_msg)

                        for i, res in enumerate(results):
                            similarity_score = 1 - res["distance"]  # Convert distance to similarity
                            with st.expander(f"🏷️ {res['collection']} | Result {i+1} | Similarity: {similarity_score:.4f} | ID: {res['id']}", expanded=(i==0)):
                                st.caption(f"**Collection:** {res['collection']} | **ID:** {res['id']}")
                                st.metric("Similarity Score", f"{similarity_score:.4f}", 
                                         delta="High match" if similarity_score > 0.8 else "Medium match" if similarity_score > 0.5 else "Low match", 
                                         delta_color="normal" if similarity_score > 0.5 else "off")
                                if res['metadata']:
                                    st.json(res['metadata'])
                                st.text_area("Content", value=res['document'], height=200, key=f"res_{res['id']}_{i}")

    except Exception as e:
        st.error(f"Error accessing ChromaDB: {e}")
        st.exception(e)

# Handle postMessage from iframe
def handle_node_click():
    """Handle node clicks from the graph visualization"""
    if 'node_click_data' in st.session_state:
        node_id = st.session_state.node_click_data
        if node_id and node_id != st.session_state.get('selected_node_id', ''):
            st.session_state.selected_node_id = node_id
            st.session_state.show_subgraph = False
            st.rerun()


# Main Streamlit App
def main():
    st.set_page_config(layout="wide", page_title="Vera Memory Explorer")
    st.title("🔗 Vera Memory Explorer")

    # Initialize session state
    if 'selected_node_id' not in st.session_state:
        st.session_state.selected_node_id = ""
    if 'show_subgraph' not in st.session_state:
        st.session_state.show_subgraph = False
    
    # Handle node clicks from JavaScript
    handle_node_click()
    
    # Initialize connections
    neo4j_driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "testpassword"))
    vector_client = VectorClient(persist_dir="/home/boejaker/langchain/app/Vera/Memory/chroma_store")

    try:
        # App mode selection
        app_mode = st.sidebar.radio("Application Mode", [
            "Neo4j Dashboard", 
            "Chroma Browser"
        ])

        # Replace the existing sidebar section in your main() function with this:

        if app_mode == "Neo4j Dashboard":
            # Visualization settings
            st.sidebar.subheader("🎨 Visualization Settings")
            color_scheme = st.sidebar.selectbox(
                "Color Scheme",
                ["pastel", "material", "vibrant", "hsl", "default"],
                index=0
            )
            
            layout_type = st.sidebar.selectbox(
                "Layout Type",
                [
                    ("default", "Default (Physics)"),
                    ("temporal_horizontal", "Temporal Horizontal (Time: Left→Right)"),
                    ("temporal_vertical", "Temporal Vertical (Time: Top→Bottom)"),
                    ("hierarchical_time", "Hierarchical Time Levels"),
                    ("circular_time", "Circular Time Ordered"),
                    ("force_time_weighted", "Force-Directed with Time Weights")
                ],
                format_func=lambda x: x[1],
                index=0,
                help="Choose how nodes are positioned. Temporal layouts work best with timestamped data."
            )
            
            # Get schema info
            with neo4j_driver.session() as session:
                node_labels = [record["label"] for record in session.run("CALL db.labels() YIELD label")]
                rel_types = [record["relationshipType"] for record in session.run("CALL db.relationshipTypes() YIELD relationshipType")]

            # Sidebar filters
            st.sidebar.subheader("🎛️ Query Controls")
            selected_label = st.sidebar.selectbox("Filter by Node Label", ["Any"] + node_labels)
            selected_rel = st.sidebar.selectbox("Filter by Relationship Type", ["Any"] + rel_types)
            limit = st.sidebar.slider("Limit results", 10, 10000, 50)

            # Time filter section
            st.sidebar.subheader("⏰ Time Filter")
            time_filter = st.sidebar.selectbox(
                "Filter by Time Range",
                ["All Time", "Last Hour", "Last 24 Hours", "Last Week", "Last Month", "Last 3 Months", "Custom Range"]
            )
            
            custom_start = None
            custom_end = None
            if time_filter == "Custom Range":
                col1, col2 = st.sidebar.columns(2)
                with col1:
                    custom_start = st.date_input("Start Date", value=datetime.now() - timedelta(days=7))
                    start_time = st.time_input("Start Time", value=datetime.min.time())
                    custom_start = datetime.combine(custom_start, start_time)
                
                with col2:
                    custom_end = st.date_input("End Date", value=datetime.now())
                    end_time = st.time_input("End Time", value=datetime.now().time())
                    custom_end = datetime.combine(custom_end, end_time)
            
            # Show time filter info
            if time_filter != "All Time":
                if time_filter == "Custom Range" and custom_start and custom_end:
                    st.sidebar.info(f"📅 Filtering: {custom_start.strftime('%Y-%m-%d %H:%M')} to {custom_end.strftime('%Y-%m-%d %H:%M')}")
                elif time_filter != "Custom Range":
                    st.sidebar.info(f"📅 Filtering: {time_filter}")

            # Node selection in sidebar
            st.sidebar.subheader("Node Selection")
            if st.session_state.get('nodes_data'):
                node_options = ["None"] + list(st.session_state.nodes_data.keys())
                current_selection = st.session_state.get('selected_node_id', "")
                
                if current_selection and current_selection in st.session_state.nodes_data:
                    current_index = node_options.index(current_selection)
                else:
                    current_index = 0
                
                selected_from_sidebar = st.sidebar.selectbox(
                    "Select Node:",
                    options=node_options,
                    format_func=lambda x: "No selection" if x == "None" else f"{x} - {st.session_state.nodes_data[x]['display_name']}" if x in st.session_state.nodes_data else x,
                    index=current_index,
                    key="sidebar_node_select"
                )
                
                if selected_from_sidebar != "None" and selected_from_sidebar != st.session_state.selected_node_id:
                    st.session_state.selected_node_id = selected_from_sidebar
                    st.session_state.show_subgraph = False
                    st.rerun()
                elif selected_from_sidebar == "None" and st.session_state.selected_node_id:
                    st.session_state.selected_node_id = ""
                    st.session_state.show_subgraph = False
                    st.rerun()
                
                # Subgraph control
                if st.session_state.selected_node_id:
                    show_subgraph = st.sidebar.checkbox("🔍 Show Subgraph", value=st.session_state.get('show_subgraph', False))
                    if show_subgraph != st.session_state.show_subgraph:
                        st.session_state.show_subgraph = show_subgraph
                        st.rerun()

            # Search functionality
            st.sidebar.subheader("🔍 Search")
            search_term = st.sidebar.text_input("Search nodes (by properties):")

            # Special buttons
            show_entire_db = st.sidebar.button("🌐 Show Entire Database")

            # Build query with proper time filtering
            time_where, time_additional = get_time_range_query_clause(time_filter, custom_start, custom_end)
            
            if show_entire_db:
                if time_where:
                    cypher_query = f"MATCH (n) {time_where} OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 1000"
                else:
                    cypher_query = "MATCH (n) OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 1000"
            elif search_term:
                search_condition = f"any(k in keys(n) WHERE toString(n[k]) CONTAINS '{search_term}')"
                if time_where:
                    # Combine search and time filters
                    combined_where = f"WHERE ({search_condition}) AND " + time_where.replace("WHERE ", "")
                else:
                    combined_where = f"WHERE {search_condition}"
                
                cypher_query = f"""
                MATCH (n)
                {combined_where}
                OPTIONAL MATCH (n)-[r]->(m)
                RETURN n, r, m
                LIMIT {limit}
                """
            else:
                # Build query based on selected filters
                base_match = "MATCH (n)"
                
                # Add label filter
                if selected_label != "Any":
                    base_match = f"MATCH (n:{selected_label})"
                
                # Add relationship filter
                if selected_rel != "Any":
                    if time_where:
                        cypher_query = f"MATCH (n)-[r:{selected_rel}]->(m) {time_where} RETURN n, r, m LIMIT {limit}"
                    else:
                        cypher_query = f"MATCH (n)-[r:{selected_rel}]->(m) RETURN n, r, m LIMIT {limit}"
                else:
                    if time_where:
                        cypher_query = f"{base_match} {time_where} OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m LIMIT {limit}"
                    else:
                        cypher_query = f"{base_match} OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m LIMIT {limit}"

            # Display query
            st.subheader("📝 Cypher Query")
            st.code(cypher_query, language="cypher")

            # Execute query with layout parameter
            if st.button("▶️ Run Query", type="primary"):
                layout_value = layout_type[0] if isinstance(layout_type, tuple) else layout_type
                execute_query_and_display(neo4j_driver, vector_client, cypher_query, color_scheme, layout_value)
        else:
            browse_chroma_store(vector_client)

        # Display node details in sidebar if selected
        if (st.session_state.get('selected_node_id') and 
            st.session_state.get('nodes_data') and 
            st.session_state.selected_node_id in st.session_state.nodes_data):
            
            node_data = st.session_state.nodes_data[st.session_state.selected_node_id]
            display_node_details(node_data, vector_client)

        # Add JavaScript to handle postMessage from iframe
        components.html("""
        <script>
        window.addEventListener('message', function(event) {
            if (event.data && event.data.type === 'node_click') {
                // Send the node click data to Streamlit
                window.parent.postMessage({
                    type: 'streamlit:setComponentValue',
                    value: event.data.nodeId
                }, '*');
            }
        });
        </script>
        """, height=0)

    finally:
        neo4j_driver.close()


if __name__ == "__main__":
    main()