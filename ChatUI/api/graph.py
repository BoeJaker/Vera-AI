# ============================================================
# Imports
# ============================================================
import logging
from fastapi import APIRouter, HTTPException
from session import sessions, get_or_create_vera
from schemas import GraphResponse, GraphNode, GraphEdge 

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
