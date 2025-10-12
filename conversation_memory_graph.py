import streamlit as st
import streamlit.components.v1 as components
import json
from memory import GraphClient

gc = GraphClient("bolt://127.0.0.1:7687", "neo4j", "")

class ConversationGraphPanel:
    def __init__(self, session_id: str, memory_system, refresh_interval=5):
        self.session_id = session_id
        self.memory = memory_system

    def get_session_subgraph(self, depth: int = 2):
        """
        Retrieve the subgraph around all memory nodes in a session.
        Returns a dict with 'nodes' and 'edges'.
        """
        session_memories = self.memory.get_session_memory(self.session_id)
        if not session_memories:
            return {"nodes": [], "edges": []}

        seed_ids = [m.id for m in session_memories]
        subgraph = gc.get_subgraph(seed_ids, depth=depth)

        # Convert nodes and edges to vis-network format
        nodes = []
        for node in subgraph.get("nodes", []):
            nodes.append({
                "id": node["id"],
                "label": node.get("labels", [""])[0],
                "color": node.get("color", "blue")
            })

        edges = []
        for rel in subgraph.get("rels", []):
            edges.append({
                "from": rel.get("start"),
                "to": rel.get("end"),
                "label": rel.get("type", "RELATED_TO")
            })
        print("Subgraph nodes:", nodes)
        print("Subgraph edges:", edges)
        return {"nodes": nodes, "edges": edges}

    def render(self, height=500, interval=5):
        """
        Render the graph as a Streamlit component using Vis Network.
        """
        subgraph = self.get_session_subgraph()
        nodes_json = json.dumps(subgraph["nodes"])
        edges_json = json.dumps(subgraph["edges"])

        html_content = f"""
        <div id="graph" style="height:{height}px; width:100%; border:1px solid lightgray;"></div>
        <script type="text/javascript" src="https://cdn.jsdelivr.net/npm/vis-network@9.1.2/standalone/umd/vis-network.min.js"></script>
        <script type="text/javascript">
            const nodes = new vis.DataSet({nodes_json});
            const edges = new vis.DataSet({edges_json});
            const container = document.getElementById('graph');
            const data = {{ nodes: nodes, edges: edges }};
            const options = {{
                nodes: {{ shape: 'dot', size: 16 }},
                edges: {{ arrows: 'to', smooth: true }},
                physics: {{ enabled: true }}
            }};
            const network = new vis.Network(container, data, options);

            // Auto-refresh interval (fetch new data from server)
            setInterval(async () => {{
                const response = await fetch(window.location.href);
                const text = await response.text();
                const parser = new DOMParser();
                const doc = parser.parseFromString(text, 'text/html');
                const newGraph = doc.getElementById('graph');
                if(newGraph) {{
                    container.innerHTML = newGraph.innerHTML;
                    new vis.Network(container, data, options);  // re-init network
                }}
            }}, {interval * 1000});
        </script>
        """

        components.html(html_content, height=height + 50, scrolling=True)
