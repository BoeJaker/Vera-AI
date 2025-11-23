# ============================================================
# Imports
# ============================================================
import logging
from fastapi import APIRouter, HTTPException
from Vera.ChatUI.api.session import sessions, get_or_create_vera
from Vera.ChatUI.api.schemas import GraphResponse, GraphNode, GraphEdge 

# ============================================================
# Logging
# ============================================================
logger = logging.getLogger(__name__)

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
                                title=f"{node_type}: {text}",
                                color=node.get("color",color),
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
    
    # Basic safety checks
    dangerous_keywords = ['DELETE', 'DETACH DELETE', 'DROP', 'REMOVE', 'SET', 'CREATE', 'MERGE']
    query_upper = query.upper()
    
    # Check for write operations (optional - remove if you want write access)
    for keyword in dangerous_keywords:
        if keyword in query_upper and 'RETURN' not in query_upper.split(keyword)[0]:
            # Allow if it's in a WHERE clause or after RETURN
            if keyword in query_upper.split('RETURN')[0] if 'RETURN' in query_upper else True:
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
    """Get database statistics."""
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
            
            return stats
            
    except Exception as e:
        logger.error(f"Stats error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))