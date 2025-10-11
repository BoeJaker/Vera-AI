import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network
import tempfile
import os
from typing import Dict, List, Any, Tuple
from datetime import datetime


class ConversationGraphPanel:
    """
    Visualizes the current conversation session as an interactive graph.
    Tracks entities, relationships, and memory items in the session.
    """
    
    def __init__(self, session_id: str, memory_system):
        """
        Args:
            session_id: The current session ID from HybridMemory
            memory_system: HybridMemory instance with the graph backend
        """
        self.session_id = session_id
        self.memory = memory_system
        self.net = None
        self.html_path = None
    
    def get_session_subgraph(self) -> Dict[str, Any]:
        """Fetch the conversation subgraph from Neo4j."""
        try:
            with self.memory.graph._driver.session() as sess:
                # Get the session node and all connected entities
                result = sess.run("""
                    MATCH (s:Session {id: $session_id})
                    OPTIONAL MATCH (s)-[r1]->(e:Entity)
                    OPTIONAL MATCH (e)-[r2]-(other:Entity)
                    RETURN s, collect(DISTINCT e) AS entities, 
                           collect(DISTINCT other) AS related_entities,
                           collect(DISTINCT r1) AS session_rels,
                           collect(DISTINCT r2) AS entity_rels
                """, session_id=self.session_id).single()
                
                if not result:
                    return {"nodes": [], "edges": []}
                
                return self._process_result(result)
        except Exception as e:
            st.error(f"Error fetching session subgraph: {e}")
            return {"nodes": [], "edges": []}
    
    def _process_result(self, result) -> Dict[str, Any]:
        """Convert Neo4j result to nodes and edges for visualization."""
        nodes = []
        edges = []
        node_ids = set()
        
        # Add session node
        if result["s"]:
            s = result["s"]
            session_node = {
                "id": s.get("id"),
                "label": f"Session\n{s.get('id', 'unknown')[-8:]}",
                "title": f"Started: {s.get('started_at', 'N/A')}",
                "color": "#FF6B6B",
                "size": 40,
                "shape": "box"
            }
            nodes.append(session_node)
            node_ids.add(s.get("id"))
        
        # Add entity nodes from session relationships
        for entity in result["entities"] or []:
            if entity is None:
                continue
            entity_id = entity.get("id")
            if entity_id not in node_ids:
                entity_node = {
                    "id": entity_id,
                    "label": entity.get("text", entity_id[:20]),
                    "title": f"Type: {entity.get('type', 'unknown')}\nText: {entity.get('text', '')[:100]}",
                    "color": "#4ECDC4",
                    "size": 25,
                    "shape": "dot"
                }
                nodes.append(entity_node)
                node_ids.add(entity_id)
                
                # Add edge from session to entity
                if result["s"]:
                    for rel in result["session_rels"] or []:
                        if rel is None:
                            continue
                        if rel.start_node.get("id") == result["s"].get("id") and rel.end_node.get("id") == entity_id:
                            edge = {
                                "from": rel.start_node.get("id"),
                                "to": entity_id,
                                "label": rel.get("rel", "RELATES_TO"),
                                "color": "#95E1D3"
                            }
                            edges.append(edge)
        
        # Add related entity nodes
        for related in result["related_entities"] or []:
            if related is None:
                continue
            related_id = related.get("id")
            if related_id not in node_ids:
                related_node = {
                    "id": related_id,
                    "label": related.get("text", related_id[:20]),
                    "title": f"Type: {related.get('type', 'unknown')}\nText: {related.get('text', '')[:100]}",
                    "color": "#A8E6CF",
                    "size": 20,
                    "shape": "dot"
                }
                nodes.append(related_node)
                node_ids.add(related_id)
        
        # Add entity-to-entity relationships
        for rel in result["entity_rels"] or []:
            if rel is None:
                continue
            start_id = rel.start_node.get("id")
            end_id = rel.end_node.get("id")
            
            if start_id in node_ids and end_id in node_ids:
                edge = {
                    "from": start_id,
                    "to": end_id,
                    "label": rel.get("rel", "RELATES_TO"),
                    "color": "#FFD93D"
                }
                edges.append(edge)
        
        return {"nodes": nodes, "edges": edges}
    
    def build_network(self, physics_enabled: bool = True, height: int = 500) -> str:
        """Build PyVis network and return HTML file path."""
        subgraph = self.get_session_subgraph()
        
        # Create network
        self.net = Network(
            height=f"{height}px",
            directed=True,
            physics=physics_enabled,
            notebook=False
        )
        
        # Configure physics
        if physics_enabled:
            self.net.physics.enabled = True
            self.net.physics.stabilization.iterations = 200
            self.net.physics.stabilization.fit = True
            self.net.physics.barnesHut.springConstant = 0.1
            self.net.physics.barnesHut.damping = 0.3
        
        # Add nodes
        for node in subgraph["nodes"]:
            self.net.add_node(
                node["id"],
                label=node["label"],
                title=node.get("title", ""),
                color=node.get("color", "#4ECDC4"),
                size=node.get("size", 25),
                shape=node.get("shape", "dot"),
                font={"size": 14, "color": "white"}
            )
        
        # Add edges
        for edge in subgraph["edges"]:
            self.net.add_edge(
                edge["from"],
                edge["to"],
                label=edge.get("label", ""),
                title=edge.get("label", ""),
                color=edge.get("color", "#95E1D3"),
                font={"size": 12}
            )
        
        # Save to temporary file
        temp_dir = tempfile.gettempdir()
        self.html_path = os.path.join(temp_dir, f"graph_{self.session_id}.html")
        
        # Configure network options
        options = """
        {
            "physics": {
                "enabled": true,
                "stabilization": {
                    "iterations": 200,
                    "fit": true
                },
                "barnesHut": {
                    "springConstant": 0.1,
                    "damping": 0.3
                }
            },
            "interaction": {
                "zoomView": true,
                "navigationButtons": true,
                "keyboard": true,
                "hover": true
            }
        }
        """
        
        self.net.show(self.html_path)
        return self.html_path
    
    def render(self, key: str = "graph_panel", physics_enabled: bool = True, height: int = 500):
        """Render the graph in Streamlit."""
        html_path = self.build_network(physics_enabled=physics_enabled, height=height)
        
        if os.path.exists(html_path):
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            components.html(html_content, height=height, scrolling=True)
        else:
            st.warning("Could not generate graph visualization")
    
    def get_graph_statistics(self) -> Dict[str, Any]:
        """Get statistics about the current session graph."""
        subgraph = self.get_session_subgraph()
        
        # Count entity types
        entity_types = {}
        for node in subgraph["nodes"]:
            if "Session" not in node.get("label", ""):
                entity_types[node.get("title", "").split("\n")[0]] = entity_types.get(node.get("title", "").split("\n")[0], 0) + 1
        
        return {
            "total_nodes": len(subgraph["nodes"]),
            "total_edges": len(subgraph["edges"]),
            "entity_types": entity_types
        }


# ============================================================
# Integration with existing ChatUI class
# ============================================================

def add_graph_panel_to_chat_ui(chat_ui_instance):
    """
    Add a graph visualization panel to the ChatUI sidebar.
    Call this after initializing ChatUI.
    
    Args:
        chat_ui_instance: The ChatUI instance from app.py
    """
    
    with st.sidebar:
        st.markdown("---")
        st.markdown("### Conversation Graph")
        
        # Get current session ID from session state
        if 'current_session_id' not in st.session_state:
            st.warning("No active session")
            return
        
        session_id = st.session_state.current_session_id
        
        # Create graph panel
        graph_panel = ConversationGraphPanel(
            session_id=session_id,
            memory_system=chat_ui_instance.vera.memory  # Assuming vera has memory attribute
        )
        
        # Statistics
        stats = graph_panel.get_graph_statistics()
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Entities", stats["total_nodes"] - 1)  # Exclude session node
        with col2:
            st.metric("Relationships", stats["total_edges"])
        
        # Graph visualization options
        physics_enabled = st.checkbox("Enable Physics Simulation", value=True)
        
        if st.button("Refresh Graph"):
            st.rerun()
        
        # Render graph
        st.markdown("**Session Conversation Graph**")
        graph_panel.render(
            key=f"graph_{session_id}",
            physics_enabled=physics_enabled,
            height=400
        )


# ============================================================
# Standalone demo
# ============================================================

if __name__ == "__main__":
    # This is a demo. In production, instantiate with real HybridMemory instance
    
    st.set_page_config(page_title="Conversation Graph Demo", layout="wide")
    st.title("Conversation Graph Visualization")
    
    st.info("This demo requires a running Neo4j instance and HybridMemory backend.")
    
    col1, col2 = st.columns([0.7, 0.3])
    
    with col2:
        st.markdown("### Controls")
        physics_enabled = st.checkbox("Physics Simulation", value=True)
        height = st.slider("Graph Height (px)", 300, 800, 500, step=50)
    
    with col1:
        st.markdown("### Graph Visualization")
        st.info("Connect to HybridMemory and pass a session_id to visualize the conversation graph")