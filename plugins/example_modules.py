
import sys
import os
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from plugin_manager import PluginBase
from common.common import plot

class Parse(PluginBase):

    @staticmethod
    def class_types():
        return( [
            "ip",
            "netblock",
            "domain",
            "subdomain",
            "ip6"
            ])

    def parse_graph(self, data):
        # Example: Add nodes and edges from Nmap data
        self.graph_manager.add_node("Host1", label="192.168.1.1")
        self.graph_manager.add_node("Host2", label="192.168.1.2")
        self.graph_manager.add_edge("Host1", "Host2", relationship="connection")

class Transformation(PluginBase):
    
    @staticmethod
    def class_types():
        return( [
            "ip",
            "netblock",
            "domain",
            "subdomain",
            "ip6"
            ])

    def transform(self, node_id, args):
        # Example: Add WHOIS data as new nodes
        self.graph_manager.add_node(f"{node_id}-whois", label="WHOIS Data")
        self.graph_manager.add_edge(node_id, f"{node_id}-whois", relationship="whois")

class delete_node(PluginBase):
    @staticmethod
    def class_types():
        return( [
            "default",
            "ip",
            "IP",
            "command",
            "file",
            "folder",
            "git",
            "netblock",
            "domain",
            "subdomain",
            "ip6",
            "contact"
            ])
    
    def execute(self, target, args):
        self.graph_manager.delete_node(target)

class delete_link(PluginBase):
    @staticmethod
    def class_types():
        return( [
            "default",
            "ip",
            "IP",
            "command",
            "file",
            "folder",
            "git",
            "netblock",
            "domain",
            "subdomain",
            "ip6",
            "contact"
            ])
    
    def execute(self, target, link):
        self.graph_manager.delete_edge(target, link)
