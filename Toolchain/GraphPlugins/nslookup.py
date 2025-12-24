"""

Returns the ip of a given url

"""
import sys
import os
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Vera.Toolchain.plugin_manager import PluginBase
from Vera.Toolchain.common.common import plot


import socket
import json

class nslookup(PluginBase):
    @staticmethod
    def class_types():
        return( [
                "ip",
                "netblock",
                "domain",
                "subdomain",
                "ip6"
                ])
        
    @staticmethod
    def description():
        return("")
    
    @staticmethod
    def output_class():
        return ["folder", "file"]

    def execute(self, domain, options):
            try:
                ip_address = socket.gethostbyname(domain)
                self.graph_manager.update_node(ip_address, {"class_type":"IP"})
                self.graph_manager.add_edge(ip_address,domain)
            except socket.gaierror as e:
                return f"Error: {e}"
            
            self.graph_manager.database.set_metadata(domain, self.metadata_type(), "RAW", json.dumps(ip_address))
            self.graph_manager.update_node(domain, ip_address)
            self.graph_manager.update_node(domain, {"nslookup":ip_address})
            return ip_address
