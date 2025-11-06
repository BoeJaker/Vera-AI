import spacy
import networkx as nx
from transformers import pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
import matplotlib.pyplot as plt
import sys
import os

# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from plugin_manager import PluginBase
from common.common import plot

class nlpText(PluginBase):

    # Load NLP models
    nlp = spacy.load("en_core_web_sm")
    summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
    
    @staticmethod
    def class_types():
        return [
            "ip",
            "IP",
            "domain",
            "subdomain",
            "contact",
            "command",
            "text",
            "Port",
        ]
    
    def execute(self, node_id, graph):
        # Display Nodes and Edges
        print("Nodes:", graph.nodes(data=True))
        print("Edges:", list(graph.edges(data=True)))
        
        # Convert node properties to text segments
        # add a value to each piece of metadata for metadata type
        text_segments = graph.nodes[node_id]["html_text"] 
        
        # Generate self.graph
        self.graph = self.text_to_networkx(text_segments, graph)

    def extract_info(self, text):
        """Extract named entities, keywords, and a summary from text."""
        doc = self.nlp(text)
        
        # Named Entity Recognition (NER)
        entities = {ent.text: ent.label_ for ent in doc.ents}
        
        # Keyword Extraction (TF-IDF)
        vectorizer = TfidfVectorizer(stop_words="english", max_features=5)
        tfidf_matrix = vectorizer.fit_transform([text])
        keywords = vectorizer.get_feature_names_out()
        
        # Summarization
        if len(text.split()) > 50:
            summary = self.summarizer(text, max_length=100, min_length=30, do_sample=False)[0]['summary_text']
        else:
            summary = text  # Use original if too short

        return {
            "Entities": entities,
            "Keywords": list(keywords),
            "Summary": summary,
            "Graph": self.graph
        }

    def text_to_networkx(self, text_segments, graph):
        """Converts multiple text segments into a self.graph representation."""
        graph = nx.Graph(graph)  # Create a copy of the input graph
        
        segment_nodes = {}  # Track segment nodes by index
        entity_nodes = {}  # Track unique entity nodes
        keyword_nodes = {}  # Track unique keyword nodes

        for i, text in enumerate(text_segments):
            info = self.extract_info(text)
            segment_id = f"Text_{i}"
            
            # Add text segment node
            graph.add_node(segment_id, type="text", summary=info["Summary"])
            segment_nodes[i] = segment_id
            
            # Add entity nodes & edges
            for entity, entity_type in info["Entities"].items():
                if entity not in entity_nodes:
                    graph.add_node(entity, type=entity_type)
                    entity_nodes[entity] = entity
                graph.add_edge(segment_id, entity, relationship="mentions")
            
            # Add keyword nodes & edges
            for keyword in info["Keywords"]:
                if keyword not in keyword_nodes:
                    graph.add_node(keyword, type="keyword")
                    keyword_nodes[keyword] = keyword
                graph.add_edge(segment_id, keyword, relationship="related_to")
        
        # Connect related text segments if they share entities or keywords
        for i, node1 in segment_nodes.items():
            for j, node2 in segment_nodes.items():
                if i >= j:
                    continue  # Avoid duplicate edges
                shared_entities = set(entity_nodes.keys()) & set(graph.neighbors(node1)) & set(graph.neighbors(node2))
                shared_keywords = set(keyword_nodes.keys()) & set(graph.neighbors(node1)) & set(graph.neighbors(node2))
                if shared_entities or shared_keywords:
                    graph.add_edge(node1, node2, relationship="related_by_content")
        
        return graph

if __name__ == '__main__':
    # Example usage with networkx graph
    G = nx.Graph()
    
    # Add nodes with text data
    for i, text in enumerate(texts):
        G.add_node(i, text_data=text)
    
    nlpp = nlpText(None, None, None)
    nlpp.execute(G, "args")
    plot(nlpp.graph)
