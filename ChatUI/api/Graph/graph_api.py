# ============================================================
# Imports
# ============================================================
import logging
import re
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from Vera.ChatUI.api.session import sessions, get_or_create_vera
from Vera.ChatUI.api.schemas import GraphResponse, GraphNode, GraphEdge 
import time

# ============================================================
# Logging
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# Timestamp Utilities
# ============================================================

def extract_timestamp_from_id(id_string: str) -> Optional[int]:
    """
    Extract timestamp (in milliseconds) from IDs like:
    - sess_1764443851177
    - mem_1764443851444
    - thought_1764443851500
    
    Returns the timestamp in milliseconds, or None if not found.
    """
    if not id_string:
        return None
    
    # Pattern: prefix_timestamp where timestamp is 13 digits (milliseconds since epoch)
    match = re.search(r'_(\d{13})(?:_|$)', id_string)
    if match:
        return int(match.group(1))
    
    # Fallback: look for any 13-digit number
    match = re.search(r'\d{13}', id_string)
    if match:
        return int(match.group(0))
    
    return None


def timestamp_to_datetime(timestamp_ms: int) -> datetime:
    """Convert millisecond timestamp to datetime object."""
    return datetime.fromtimestamp(timestamp_ms / 1000.0)


def datetime_to_timestamp(dt: datetime) -> int:
    """Convert datetime object to millisecond timestamp."""
    return int(dt.timestamp() * 1000)


def format_timestamp(timestamp_ms: int) -> str:
    """Format timestamp for display."""
    dt = timestamp_to_datetime(timestamp_ms)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def get_cypher_time_filter_multifield(
    node_var: str = "n",
    time_field: str = "auto",
    after: Optional[datetime] = None,
    before: Optional[datetime] = None
) -> tuple[str, dict]:
    """Generate Cypher WHERE clause and parameters for time-based filtering with multiple field support."""
    if not after and not before:
        return "", {}
    
    params = {}
    
    # Convert datetimes to both milliseconds and ISO strings
    if after:
        after_ts = datetime_to_timestamp(after)
        after_iso = after.isoformat()
        params["after_ts"] = after_ts
        params["after_iso"] = after_iso
    
    if before:
        before_ts = datetime_to_timestamp(before)
        before_iso = before.isoformat()
        params["before_ts"] = before_ts
        params["before_iso"] = before_iso
    
    # Build the time extraction expression based on field selection
    if time_field == "id":
        # Extract from ID only
        time_expr = f"toInteger(substring({node_var}.id, size(split({node_var}.id, '_')[0]) + 1, 13))"
        conditions = []
        if after:
            conditions.append(f"{time_expr} >= $after_ts")
        if before:
            conditions.append(f"{time_expr} <= $before_ts")
        where_clause = " AND ".join(conditions)
        
    elif time_field in ["created_at", "updated_at", "timestamp"]:
        # Handle both datetime objects and string dates
        # Try to convert to datetime if it's a string, otherwise use as-is
        time_expr = f"""CASE 
            WHEN {node_var}.{time_field} IS NOT NULL 
            THEN coalesce(
                datetime({node_var}.{time_field}),
                datetime(replace({node_var}.{time_field}, ' ', 'T'))
            )
            ELSE null
        END"""
        
        conditions = []
        if after:
            conditions.append(f"{time_expr} >= datetime($after_iso)")
        if before:
            conditions.append(f"{time_expr} <= datetime($before_iso)")
        where_clause = f"{node_var}.{time_field} IS NOT NULL AND " + " AND ".join(conditions)
        
    else:  # "auto" - fallback chain
        # Use COALESCE to try multiple sources in order
        # Priority: ID timestamp -> created_at -> updated_at -> timestamp
        
        # Build the COALESCE expression for timestamp extraction
        id_ts_expr = f"toInteger(substring({node_var}.id, size(split({node_var}.id, '_')[0]) + 1, 13))"
        
        # Convert datetime properties to millisecond timestamps for comparison
        # Handle both datetime objects and string dates
        def make_ts_expr(field):
            return f"""toInteger(coalesce(
                datetime({node_var}.{field}),
                datetime(replace({node_var}.{field}, ' ', 'T'))
            ).epochMillis)"""
        
        created_ts_expr = make_ts_expr("created_at")
        updated_ts_expr = make_ts_expr("updated_at")
        timestamp_ts_expr = make_ts_expr("timestamp")
        
        # COALESCE to get first available timestamp
        time_expr = f"""COALESCE(
            CASE WHEN {node_var}.id =~ '.*_\\d{{13}}.*' THEN {id_ts_expr} ELSE null END,
            CASE WHEN {node_var}.created_at IS NOT NULL THEN {created_ts_expr} ELSE null END,
            CASE WHEN {node_var}.updated_at IS NOT NULL THEN {updated_ts_expr} ELSE null END,
            CASE WHEN {node_var}.timestamp IS NOT NULL THEN {timestamp_ts_expr} ELSE null END
        )"""
        
        conditions = []
        if after:
            conditions.append(f"{time_expr} >= $after_ts")
        if before:
            conditions.append(f"{time_expr} <= $before_ts")
        
        where_clause = f"{time_expr} IS NOT NULL AND " + " AND ".join(conditions)
    
    return where_clause, params

# ============================================================
# Router setup
# ============================================================
router = APIRouter(prefix="/api/graph", tags=["graph"])

# ============================================================
# Graph Endpoints
# ============================================================
@router.get("/session/{session_id}", response_model=GraphResponse)
async def get_session_graph(session_id: str):
    """Get the knowledge graph for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    vera = get_or_create_vera(session_id)
    actual_session_id = vera.sess.id
    
    try:
        driver = vera.mem.graph._driver
        
        with driver.session() as db_sess:
            # Get all nodes matching session_id and connected nodes within 3 hops
            result = db_sess.run("""
                MATCH (n)
                WHERE n.session_id = $session_id OR n.extracted_from_session = $session_id
                OPTIONAL MATCH path = (n)-[r*0..3]-(connected)
                WITH collect(DISTINCT connected) + collect(DISTINCT n) AS nodes,
                     collect(DISTINCT relationships(path)) AS rels
                UNWIND rels AS rel_list
                UNWIND rel_list AS rel
                RETURN DISTINCT nodes, collect(DISTINCT rel) AS relationships
            """, {"session_id": actual_session_id})
            
            nodes_list = []
            edges = []
            seen_nodes = set()
            seen_edges = set()
            
            # Process the query results
            for record in result:
                # Process all nodes
                all_nodes = record.get("nodes", [])
                for node in all_nodes:
                    if node and node.get("id"):
                        node_id = node.get("id", "")
                        if node_id and node_id not in seen_nodes:
                            seen_nodes.add(node_id)
                            
                            properties = dict(node)
                            logger.debug(properties)
                            text = properties.get("text", properties.get("name", node_id))
                            node_type = properties.get("type", "node")
                            
                            # Determine color based on type
                            color = "#3b82f6"  # Default blue
                            if node_type in ["thought", "memory", "Thought","Memory"]:
                                color = "#f59e0b"  # Orange
                            elif node_type in ["decision", "Decision"]:
                                color = "#ef4444"  # Red
                            elif node_type in ["class", "Class"]:
                                color = "#2d8cf0"  # Blue
                            elif node_type in ["Plan", "plan"]:
                                color = "#8b5cf6"  # Purple
                            elif node_type in ["Tool", "tool"]:
                                color = "#f97316"  # Deep Orange  
                            elif node_type in ["Process", "process"]:
                                color = "#e879f9"  # Pink
                            elif node_type in ["File", "file"]:
                                color = "#f43f5e"  # Rose
                            elif node_type in ["Webpage", "webpage"]:
                                color = "#60a5fa"  # Light Blue
                            elif node_type in ["Document", "document"]:
                                color = "#34d399"  # Emerald
                            elif node_type in ["Query", "query"]:
                                color = "#32B39D"  # Turquoise
                            elif node_type == "extracted_entity":
                                color = "#07c3e4"  # Cyan
                            elif node_type == ["Session", "session"]:
                                color = "#3f1b92"  # Purple
                            elif "Entity" in properties.get("labels", []):
                                color = "#10b93a"  # Green

                            
                            nodes_list.append(GraphNode(
                                id=node_id,
                                label=node_type,
                                title=f"{node_type}: {text[:min(len(text), 20)]}",
                                color=node.get("color", color),
                                properties=properties,
                                size=min(properties.get("importance", 20), 40)
                            ))
                
                # Process all relationships
                all_relationships = record.get("relationships", [])
                for rel in all_relationships:
                    if rel:
                        try:
                            # Get source and target nodes
                            start_node = rel.start_node
                            end_node = rel.end_node
                            
                            start_id = start_node.get("id", "") if start_node else ""
                            end_id = end_node.get("id", "") if end_node else ""
                            
                            if start_id and end_id:
                                # Get relationship label
                                rel_props = dict(rel) if hasattr(rel, 'items') else {}
                                rel_label = rel_props.get("rel", getattr(rel, "type", "RELATED"))
                                
                                edge_key = f"{start_id}-{rel_label}->{end_id}"
                                if edge_key not in seen_edges:
                                    seen_edges.add(edge_key)
                                    edges.append(GraphEdge(
                                        **{
                                            "from": start_id,
                                            "to": end_id,
                                            "label": str(rel_label)
                                        }
                                    ))
                        except Exception as e:
                            logger.debug(f"Error processing relationship: {e}")
                            continue
            
            logger.info(f"Returning {len(nodes_list)} nodes and {len(edges)} edges for session {actual_session_id}")
            return GraphResponse(
                nodes=nodes_list,
                edges=edges,
                stats={
                    "node_count": len(nodes_list),
                    "edge_count": len(edges),
                    "session_id": actual_session_id
                }
            )
            
    except Exception as e:
        logger.error(f"Graph error: {str(e)}", exc_info=True)
        # Return minimal graph with session node only
        return GraphResponse(
            nodes=[GraphNode(
                id=actual_session_id,
                label=f"Session {actual_session_id[-8:]}",
                title=f"Session: {actual_session_id}",
                properties={},
                color="#8b5cf6",
                size=30
            )],
            edges=[],
            stats={"node_count": 1, "edge_count": 0, "session_id": actual_session_id}
        )

# ============================================================
# Cypher Query Endpoint 
# ============================================================
from pydantic import BaseModel
from typing import Optional, List, Any, Dict

# ============================================================
# New Schemas for Cypher Queries
# ============================================================
class CypherQueryRequest(BaseModel):
    query: str
    parameters: Optional[Dict[str, Any]] = {}
    limit: Optional[int] = 500  # Safety limit

class CypherQueryResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    raw_results: Optional[List[Dict[str, Any]]] = []
    stats: Dict[str, Any]
    query_executed: str
    success: bool
    error: Optional[str] = None

# ============================================================
# Cypher Query Endpoint
# ============================================================
@router.post("/cypher", response_model=CypherQueryResponse)
async def execute_cypher_query(request: CypherQueryRequest):
    """
    Execute a custom Cypher query against the Neo4j database.
    Returns nodes and edges extracted from the results.
    """
    query = request.query.strip()
    
    # Improved safety checks - only block actual write operations at statement boundaries
    # This avoids false positives from property names like "created_at", "created_time", etc.
    dangerous_keywords = ['DELETE', 'DETACH', 'DROP', 'REMOVE', 'SET', 'CREATE', 'MERGE']
    query_upper = query.upper()
    
    # Check for write operations as standalone clauses (not in property names)
    for keyword in dangerous_keywords:
        # Create pattern that matches keyword as a Cypher clause
        # Must be preceded by whitespace, start of string, or newline
        # Must be followed by whitespace or end of string
        pattern = r'(?:^|\s|;)\s*' + re.escape(keyword) + r'(?:\s|$)'
        
        if re.search(pattern, query_upper):
            # Double-check it's not part of a property name
            # Look for patterns like "n.created_at" or "created_time"
            if not re.search(r'\w+' + re.escape(keyword.lower()), query.lower()):
                return CypherQueryResponse(
                    nodes=[],
                    edges=[],
                    raw_results=[],
                    stats={"error": f"Write operation '{keyword}' not allowed in read-only mode"},
                    query_executed=query,
                    success=False,
                    error=f"Write operation '{keyword}' not allowed. Use read-only queries."
                )
    
    # Inject LIMIT if not present for safety
    if 'LIMIT' not in query_upper:
        query = f"{query} LIMIT {request.limit}"
    
    try:
        # Get a Vera instance to access the graph driver
        # You might need to adjust this based on your session management
        vera = None
        for session_id in sessions:
            vera = get_or_create_vera(session_id)
            break
        
        if not vera:
            # Create a temporary connection if no session exists
            # Adjust this to match your Neo4j connection setup
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(
                "bolt://localhost:7687",  # Adjust your Neo4j URI
                auth=("neo4j", "password")  # Adjust credentials
            )
        else:
            driver = vera.mem.graph._driver
        
        nodes_list = []
        edges = []
        raw_results = []
        seen_nodes = set()
        seen_edges = set()
        
        with driver.session() as db_sess:
            result = db_sess.run(query, request.parameters or {})
            
            for record in result:
                # Store raw result
                raw_record = {}
                
                for key in record.keys():
                    value = record[key]
                    
                    # Process the value based on type
                    if hasattr(value, 'labels'):  # It's a Node
                        node = value
                        node_id = node.get("id", str(node.element_id))
                        
                        if node_id not in seen_nodes:
                            seen_nodes.add(node_id)
                            properties = dict(node)
                            labels = list(node.labels) if hasattr(node, 'labels') else []
                            
                            # Determine display text and color
                            text = properties.get("text", properties.get("name", node_id))
                            node_type = properties.get("type", labels[0] if labels else "node")
                            
                            color = get_node_color(node_type, properties, labels)
                            
                            properties["labels"] = labels
                            logger.debug(properties)
                            nodes_list.append(GraphNode(
                                id=node_id,
                                label=node_type,
                                title=f"{node_type}: {text[:100] if len(str(text)) > 100 else text}",
                                color=properties.get("color", color),
                                properties=properties,
                                size=min(properties.get("importance", 25), 40)
                            ))
                        
                        raw_record[key] = {"type": "node", "id": node_id, "labels": labels}
                    
                    elif hasattr(value, 'type'):  # It's a Relationship
                        rel = value
                        try:
                            start_node = rel.start_node
                            end_node = rel.end_node
                            
                            start_id = start_node.get("id", str(rel.start_node.element_id))
                            end_id = end_node.get("id", str(rel.end_node.element_id))
                            rel_type = rel.type
                            
                            edge_key = f"{start_id}-{rel_type}->{end_id}"
                            if edge_key not in seen_edges:
                                seen_edges.add(edge_key)
                                edges.append(GraphEdge(
                                    **{
                                        "from": start_id,
                                        "to": end_id,
                                        "label": str(rel_type)
                                    }
                                ))
                            
                            raw_record[key] = {"type": "relationship", "rel_type": rel_type}
                        except Exception as e:
                            logger.debug(f"Error processing relationship: {e}")
                    
                    elif hasattr(value, '__iter__') and not isinstance(value, (str, dict)):
                        # It's a path or list
                        for item in value:
                            if hasattr(item, 'labels'):  # Node in path
                                process_node_from_path(item, nodes_list, seen_nodes)
                            elif hasattr(item, 'type'):  # Relationship in path
                                process_rel_from_path(item, edges, seen_edges)
                        raw_record[key] = {"type": "path/list", "length": len(list(value))}
                    
                    else:
                        # Scalar value
                        raw_record[key] = value
                
                raw_results.append(raw_record)
        
        return CypherQueryResponse(
            nodes=nodes_list,
            edges=edges,
            raw_results=raw_results[:100],  # Limit raw results for response size
            stats={
                "node_count": len(nodes_list),
                "edge_count": len(edges),
                "result_count": len(raw_results)
            },
            query_executed=query,
            success=True
        )
        
    except Exception as e:
        logger.error(f"Cypher query error: {str(e)}", exc_info=True)
        return CypherQueryResponse(
            nodes=[],
            edges=[],
            raw_results=[],
            stats={},
            query_executed=query,
            success=False,
            error=str(e)
        )


def get_node_color(node_type: str, properties: dict, labels: list) -> str:
    """Determine node color based on type and labels."""
    color_map = {
        "thought": "#f59e0b",
        "memory": "#f59e0b",
        "decision": "#ef4444",
        "class": "#2d8cf0",
        "plan": "#8b5cf6",
        "tool": "#f97316",
        "process": "#e879f9",
        "file": "#f43f5e",
        "webpage": "#60a5fa",
        "document": "#34d399",
        "query": "#32B39D",
        "extracted_entity": "#07c3e4",
        "session": "#3f1b92",
        "entity": "#10b93a",
        "person": "#ec4899",
        "organization": "#8b5cf6",
        "location": "#14b8a6",
        "event": "#f97316",
        "concept": "#6366f1",
    }
    
    # Check node_type
    type_lower = node_type.lower() if node_type else ""
    if type_lower in color_map:
        return color_map[type_lower]
    
    # Check labels
    for label in labels:
        label_lower = label.lower() if label else ""
        if label_lower in color_map:
            return color_map[label_lower]
    
    # Check if Entity is in labels
    if "Entity" in labels or "entity" in labels:
        return "#10b93a"
    
    return "#3b82f6"  # Default blue


def process_node_from_path(node, nodes_list, seen_nodes):
    """Process a node from a path result."""
    node_id = node.get("id", str(node.element_id))
    if node_id not in seen_nodes:
        seen_nodes.add(node_id)
        properties = dict(node)
        labels = list(node.labels) if hasattr(node, 'labels') else []
        text = properties.get("text", properties.get("name", node_id))
        node_type = properties.get("type", labels[0] if labels else "node")
        color = get_node_color(node_type, properties, labels)
        
        nodes_list.append(GraphNode(
            id=node_id,
            label=node_type,
            title=f"{node_type}: {text[:100] if len(str(text)) > 100 else text}",
            color=properties.get("color", color),
            properties=properties,
            size=min(properties.get("importance", 25), 40)
        ))


def process_rel_from_path(rel, edges, seen_edges):
    """Process a relationship from a path result."""
    try:
        start_id = rel.start_node.get("id", str(rel.start_node.element_id))
        end_id = rel.end_node.get("id", str(rel.end_node.element_id))
        rel_type = rel.type
        
        edge_key = f"{start_id}-{rel_type}->{end_id}"
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            edges.append(GraphEdge(
                **{
                    "from": start_id,
                    "to": end_id,
                    "label": str(rel_type)
                }
            ))
    except Exception:
        pass


# ============================================================
# Time-Based Query Endpoints
# ============================================================
@router.get("/timerange", response_model=GraphResponse)
async def get_nodes_by_timerange(
    after: Optional[str] = Query(None, description="ISO format datetime (e.g., 2024-01-01T00:00:00)"),
    before: Optional[str] = Query(None, description="ISO format datetime (e.g., 2024-12-31T23:59:59)"),
    node_types: Optional[str] = Query(None, description="Comma-separated node types to filter (e.g., 'thought,memory')"),
    time_field: str = Query("auto", description="Time field to use: 'auto', 'id', 'created_at', 'updated_at', 'timestamp'"),
    max_nodes: int = Query(100, description="Maximum number of nodes to return", le=1000)
):
    """
    Get nodes created within a specific time range based on multiple timestamp sources.
    
    Time field options:
    - auto: Try id -> created_at -> updated_at -> timestamp (default)
    - id: Extract timestamp from node ID only
    - created_at: Use created_at property
    - updated_at: Use updated_at property  
    - timestamp: Use timestamp property
    
    Examples:
    - /api/graph/timerange?after=2024-01-01T00:00:00
    - /api/graph/timerange?after=2024-01-01T00:00:00&time_field=created_at
    - /api/graph/timerange?after=2024-01-01T00:00:00&before=2024-01-31T23:59:59&node_types=thought,memory
    """
    try:
        # Parse datetime parameters
        after_dt = datetime.fromisoformat(after) if after else None
        before_dt = datetime.fromisoformat(before) if before else None
        
        # Get time filter with multi-field support
        time_where, time_params = get_cypher_time_filter_multifield(
            node_var="n",
            time_field=time_field,
            after=after_dt,
            before=before_dt
        )
        
        # Build type filter
        type_filter = ""
        if node_types:
            types_list = [t.strip() for t in node_types.split(',')]
            type_filter = "n.type IN $types"
            time_params["types"] = types_list
        
        # Combine filters
        where_clause = f"WHERE {time_where}" if time_where else ""
        if type_filter:
            where_clause = f"{where_clause} AND {type_filter}" if where_clause else f"WHERE {type_filter}"
        
        # Build ordering based on time_field
        if time_field == "id":
            order_expr = "toInteger(substring(n.id, size(split(n.id, '_')[0]) + 1, 13))"
        elif time_field in ["created_at", "updated_at", "timestamp"]:
            order_expr = f"n.{time_field}"
        else:  # auto
            # Use COALESCE for ordering too
            id_ts_expr = "toInteger(substring(n.id, size(split(n.id, '_')[0]) + 1, 13))"
            created_ts_expr = "toInteger(datetime(n.created_at).epochMillis)"
            updated_ts_expr = "toInteger(datetime(n.updated_at).epochMillis)"
            timestamp_ts_expr = "toInteger(datetime(n.timestamp).epochMillis)"
            
            order_expr = f"""COALESCE(
                CASE WHEN n.id =~ '.*_\\d{{13}}.*' THEN {id_ts_expr} ELSE null END,
                CASE WHEN n.created_at IS NOT NULL THEN {created_ts_expr} ELSE null END,
                CASE WHEN n.updated_at IS NOT NULL THEN {updated_ts_expr} ELSE null END,
                CASE WHEN n.timestamp IS NOT NULL THEN {timestamp_ts_expr} ELSE null END
            )"""
        
        # Build query
        query = f"""
            MATCH (n)
            {where_clause}
            WITH n, {order_expr} as sort_time
            ORDER BY sort_time DESC
            LIMIT $max_nodes
            OPTIONAL MATCH (n)-[r]-(connected)
            RETURN n, collect(DISTINCT r) as relationships, collect(DISTINCT connected) as connected_nodes
        """
        
        time_params["max_nodes"] = max_nodes
        
        # Get Vera instance
        vera = None
        for session_id in sessions:
            vera = get_or_create_vera(session_id)
            break
        
        if not vera:
            raise HTTPException(status_code=500, detail="No active session")
        
        driver = vera.mem.graph._driver
        
        nodes_list = []
        edges = []
        seen_nodes = set()
        seen_edges = set()
        
        with driver.session() as db_sess:
            result = db_sess.run(query, time_params)
            
            for record in result:
                # Process main node
                node = record["n"]
                if node:
                    node_id = node.get("id", str(node.element_id))
                    if node_id not in seen_nodes:
                        seen_nodes.add(node_id)
                        properties = dict(node)
                        labels = list(node.labels) if hasattr(node, 'labels') else []
                        
                        text = properties.get("text", properties.get("name", node_id))
                        node_type = properties.get("type", labels[0] if labels else "node")
                        color = get_node_color(node_type, properties, labels)
                        
                        # Extract timestamp for display (try all sources)
                        timestamp = extract_timestamp_from_id(node_id)
                        if timestamp:
                            properties["_timestamp"] = format_timestamp(timestamp)
                            properties["_timestamp_source"] = "id"
                        elif properties.get("created_at"):
                            try:
                                dt = datetime.fromisoformat(str(properties["created_at"]))
                                properties["_timestamp"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                                properties["_timestamp_source"] = "created_at"
                            except:
                                pass
                        elif properties.get("updated_at"):
                            try:
                                dt = datetime.fromisoformat(str(properties["updated_at"]))
                                properties["_timestamp"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                                properties["_timestamp_source"] = "updated_at"
                            except:
                                pass
                        elif properties.get("timestamp"):
                            try:
                                dt = datetime.fromisoformat(str(properties["timestamp"]))
                                properties["_timestamp"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                                properties["_timestamp_source"] = "timestamp"
                            except:
                                pass
                        
                        nodes_list.append(GraphNode(
                            id=node_id,
                            label=node_type,
                            title=f"{node_type}: {text[:100] if len(str(text)) > 100 else text}",
                            color=properties.get("color", color),
                            properties=properties,
                            size=min(properties.get("importance", 25), 40)
                        ))
                
                # Process connected nodes
                for connected in record.get("connected_nodes", []):
                    if connected:
                        node_id = connected.get("id", str(connected.element_id))
                        if node_id not in seen_nodes:
                            seen_nodes.add(node_id)
                            properties = dict(connected)
                            labels = list(connected.labels) if hasattr(connected, 'labels') else []
                            
                            text = properties.get("text", properties.get("name", node_id))
                            node_type = properties.get("type", labels[0] if labels else "node")
                            color = get_node_color(node_type, properties, labels)
                            
                            timestamp = extract_timestamp_from_id(node_id)
                            if timestamp:
                                properties["_timestamp"] = format_timestamp(timestamp)
                            
                            nodes_list.append(GraphNode(
                                id=node_id,
                                label=node_type,
                                title=f"{node_type}: {text[:100] if len(str(text)) > 100 else text}",
                                color=properties.get("color", color),
                                properties=properties,
                                size=min(properties.get("importance", 25), 40)
                            ))
                
                # Process relationships
                for rel in record.get("relationships", []):
                    if rel:
                        try:
                            start_id = rel.start_node.get("id", str(rel.start_node.element_id))
                            end_id = rel.end_node.get("id", str(rel.end_node.element_id))
                            rel_type = rel.type
                            
                            edge_key = f"{start_id}-{rel_type}->{end_id}"
                            if edge_key not in seen_edges:
                                seen_edges.add(edge_key)
                                edges.append(GraphEdge(
                                    **{
                                        "from": start_id,
                                        "to": end_id,
                                        "label": str(rel_type)
                                    }
                                ))
                        except Exception as e:
                            logger.debug(f"Error processing relationship: {e}")
        
        return GraphResponse(
            nodes=nodes_list,
            edges=edges,
            stats={
                "node_count": len(nodes_list),
                "edge_count": len(edges),
                "after": after,
                "before": before,
                "node_types": node_types,
                "time_field": time_field
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid datetime format: {str(e)}")
    except Exception as e:
        logger.error(f"Time range query error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recent", response_model=GraphResponse)
async def get_recent_nodes(
    hours: int = Query(24, description="Number of hours to look back", ge=1, le=168),
    node_types: Optional[str] = Query(None, description="Comma-separated node types to filter"),
    time_field: str = Query("auto", description="Time field to use: 'auto', 'id', 'created_at', 'updated_at', 'timestamp'"),
    max_nodes: int = Query(50, description="Maximum number of nodes to return", le=500)
):
    """
    Get nodes created in the last N hours based on multiple timestamp sources.
    
    Examples:
    - /api/graph/recent?hours=24
    - /api/graph/recent?hours=1&node_types=thought,decision&time_field=created_at
    """
    from datetime import timedelta
    
    now = datetime.now()
    after = now - timedelta(hours=hours)
    
    # Reuse the timerange endpoint logic
    return await get_nodes_by_timerange(
        after=after.isoformat(),
        before=None,
        node_types=node_types,
        time_field=time_field,
        max_nodes=max_nodes
    )
# ============================================================
# Additional Utility Endpoints
# ============================================================
@router.get("/schema")
async def get_database_schema():
    """Get the database schema (node labels and relationship types)."""
    try:
        vera = None
        for session_id in sessions:
            vera = get_or_create_vera(session_id)
            break
        
        if not vera:
            raise HTTPException(status_code=500, detail="No active session to query schema")
        
        driver = vera.mem.graph._driver
        
        with driver.session() as db_sess:
            # Get all node labels
            labels_result = db_sess.run("CALL db.labels()")
            labels = [record[0] for record in labels_result]
            
            # Get all relationship types
            rels_result = db_sess.run("CALL db.relationshipTypes()")
            rel_types = [record[0] for record in rels_result]
            
            # Get property keys
            props_result = db_sess.run("CALL db.propertyKeys()")
            property_keys = [record[0] for record in props_result]
            
            # Get node counts per label
            label_counts = {}
            for label in labels:
                count_result = db_sess.run(f"MATCH (n:`{label}`) RETURN count(n) as count")
                label_counts[label] = count_result.single()["count"]
            
            return {
                "labels": labels,
                "relationship_types": rel_types,
                "property_keys": property_keys,
                "label_counts": label_counts,
                "total_nodes": sum(label_counts.values()),
                "total_relationships": db_sess.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
            }
            
    except Exception as e:
        logger.error(f"Schema error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_database_stats():
    """Get database statistics including timestamp-based metrics."""
    try:
        vera = None
        for session_id in sessions:
            vera = get_or_create_vera(session_id)
            break
        
        if not vera:
            raise HTTPException(status_code=500, detail="No active session")
        
        driver = vera.mem.graph._driver
        
        with driver.session() as db_sess:
            stats = {}
            
            # Total nodes
            stats["total_nodes"] = db_sess.run(
                "MATCH (n) RETURN count(n) as count"
            ).single()["count"]
            
            # Total relationships
            stats["total_relationships"] = db_sess.run(
                "MATCH ()-[r]->() RETURN count(r) as count"
            ).single()["count"]
            
            # Nodes by type
            type_result = db_sess.run("""
                MATCH (n)
                WITH coalesce(n.type, labels(n)[0], 'unknown') as type
                RETURN type, count(*) as count
                ORDER BY count DESC
                LIMIT 20
            """)
            stats["nodes_by_type"] = {r["type"]: r["count"] for r in type_result}
            
            # Relationships by type
            rel_result = db_sess.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(*) as count
                ORDER BY count DESC
                LIMIT 20
            """)
            stats["relationships_by_type"] = {r["type"]: r["count"] for r in rel_result}
            
            # Time-based statistics
            # Get oldest and newest nodes based on ID timestamps
            time_stats_query = """
                MATCH (n)
                WHERE n.id IS NOT NULL AND n.id =~ '.*_\\d{13}.*'
                WITH n, toInteger(substring(n.id, size(split(n.id, '_')[0]) + 1, 13)) as ts
                WHERE ts IS NOT NULL AND ts > 0
                RETURN 
                    min(ts) as oldest_timestamp,
                    max(ts) as newest_timestamp,
                    count(*) as nodes_with_timestamps
            """
            
            time_result = db_sess.run(time_stats_query).single()
            if time_result and time_result["nodes_with_timestamps"] > 0:
                oldest_ts = time_result["oldest_timestamp"]
                newest_ts = time_result["newest_timestamp"]
                
                stats["time_range"] = {
                    "oldest": format_timestamp(oldest_ts),
                    "newest": format_timestamp(newest_ts),
                    "oldest_timestamp_ms": oldest_ts,
                    "newest_timestamp_ms": newest_ts,
                    "nodes_with_timestamps": time_result["nodes_with_timestamps"]
                }
                
                # Activity over last 24 hours
                now_ts = datetime_to_timestamp(datetime.now())
                day_ago_ts = now_ts - (24 * 60 * 60 * 1000)
                
                activity_result = db_sess.run("""
                    MATCH (n)
                    WHERE n.id IS NOT NULL AND n.id =~ '.*_\\d{13}.*'
                    WITH n, toInteger(substring(n.id, size(split(n.id, '_')[0]) + 1, 13)) as ts
                    WHERE ts IS NOT NULL AND ts >= $day_ago_ts
                    RETURN count(*) as count_24h
                """, {"day_ago_ts": day_ago_ts}).single()
                
                stats["time_range"]["nodes_last_24h"] = activity_result["count_24h"] if activity_result else 0
            
            return stats
            
    except Exception as e:
        logger.error(f"Stats error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

        # ============================================================
# Node and Edge Creation Endpoints
# ============================================================

class CreateNodeRequest(BaseModel):
    label: str
    type: str
    description: Optional[str] = None
    x: float = 0
    y: float = 0
    session_id: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None

class CreateEdgeRequest(BaseModel):
    source_id: str
    target_id: str
    relationship_type: str
    label: Optional[str] = None
    session_id: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    
@router.post("/node/create")
async def create_node(request: CreateNodeRequest, force_create: bool = False):
    """
    Create a new node in the Neo4j graph.
    If force_create=False and duplicate exists, returns error with existing node info.
    If force_create=True, creates with unique ID even if name/type match.
    """
    try:
        logger.info(f"=== CREATE NODE REQUEST ===")
        logger.info(f"Request: {request.model_dump()}, force_create: {force_create}")
        
        session_id = request.session_id or list(sessions.keys())[0] if sessions else None
        if not session_id:
            raise HTTPException(status_code=400, detail="No active session")
        
        vera = get_or_create_vera(session_id)
        logger.info(f"Got Vera instance for session {session_id}")
        
        # Check for duplicate unless force_create is True
        if not force_create:
            with vera.mem.graph._driver.session() as db_sess:
                existing = db_sess.run("""
                    MATCH (n:Entity)
                    WHERE n.name = $name AND n.type = $type
                    RETURN n.id AS id, properties(n) AS properties
                    LIMIT 1
                """, {
                    "name": request.label,
                    "type": request.type
                }).single()
                
                if existing:
                    logger.warning(f"Duplicate node found: {existing['id']}")
                    raise HTTPException(
                        status_code=409,  # Conflict
                        detail={
                            "error": "duplicate",
                            "message": f"Node with name '{request.label}' and type '{request.type}' already exists",
                            "existing_node": {
                                "id": existing["id"],
                                "properties": dict(existing["properties"])
                            }
                        }
                    )
        
        node_id = f"node_{int(time.time() * 1000)}"
        properties = request.properties or {}
        properties.update({
            "text": request.label,
            "name": request.label,
            "type": request.type,
            "description": request.description or "",
            "created_at": datetime.utcnow().isoformat(),
        })
        
        logger.info(f"Creating node {node_id} with properties: {properties}")
        
        # Create node
        node = vera.mem.upsert_entity(
            entity_id=node_id,
            etype=request.type,
            labels=[request.type],
            properties=properties
        )
        
        logger.info(f"Node created: {node}")
        
        # Verify it was created
        with vera.mem.graph._driver.session() as db_sess:
            verify = db_sess.run("MATCH (n {id: $id}) RETURN n", {"id": node_id}).single()
            logger.info(f"Verification query result: {verify}")
            if not verify:
                raise Exception("Node creation failed - not found in database")
        
        return {
            "success": True,
            "node_id": node_id,
            "verified": verify is not None
        }
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"CREATE NODE ERROR: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/edge/create")
async def create_edge(request: CreateEdgeRequest):
    """
    Create a new edge between two nodes in the Neo4j graph.
    Uses the HybridMemory API for safe, validated creation.
    """
    try:
        # Get or create Vera instance
        session_id = request.session_id or list(sessions.keys())[0] if sessions else None
        if not session_id:
            raise HTTPException(status_code=400, detail="No active session. Please specify session_id or start a session.")
        
        vera = get_or_create_vera(session_id)
        
        # Prepare edge properties
        properties = request.properties or {}
        properties.update({
            "label": request.label or request.relationship_type,
            "created_at": datetime.utcnow().isoformat(),
            "created_by": "user",
            "session_id": session_id
        })
        
        # Create edge using HybridMemory
        vera.mem.link(
            src=request.source_id,
            dst=request.target_id,
            rel=request.relationship_type,
            properties=properties
        )
        
        logger.info(f"Created edge {request.source_id} -[{request.relationship_type}]-> {request.target_id}")
        
        return {
            "success": True,
            "edge": {
                "from": request.source_id,
                "to": request.target_id,
                "relationship": request.relationship_type,
                "label": request.label or request.relationship_type,
                "properties": properties
            }
        }
        
    except Exception as e:
        logger.error(f"Error creating edge: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

        # Add this new endpoint before @router.post("/node/create")

@router.post("/node/check-duplicate")
async def check_node_duplicate(request: CreateNodeRequest):
    """
    Check if a node with the same name and type already exists.
    Returns existing node info if found.
    """
    try:
        session_id = request.session_id or list(sessions.keys())[0] if sessions else None
        if not session_id:
            raise HTTPException(status_code=400, detail="No active session")
        
        vera = get_or_create_vera(session_id)
        
        # Check for existing node
        with vera.mem.graph._driver.session() as db_sess:
            result = db_sess.run("""
                MATCH (n:Entity)
                WHERE n.name = $name AND n.type = $type
                RETURN n.id AS id, n.name AS name, n.type AS type, 
                       labels(n) AS labels, properties(n) AS properties
                LIMIT 1
            """, {
                "name": request.label,
                "type": request.type
            }).single()
            
            if result:
                return {
                    "exists": True,
                    "node": {
                        "id": result["id"],
                        "name": result["name"],
                        "type": result["type"],
                        "labels": result["labels"],
                        "properties": dict(result["properties"])
                    }
                }
            else:
                return {"exists": False}
                
    except Exception as e:
        logger.error(f"Error checking duplicate: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))