"""

Returns the route to a given URL and constructs a network graph of the path.

"""
import sys
import os
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Vera.Toolchain.plugin_manager import PluginBase
from Vera.Toolchain.common.common import plot

from typing import List, Dict, Union
import subprocess
import networkx as nx
import re
import json

class Traceroutev2(PluginBase):
    
    @staticmethod
    def class_types():
        return( [
        "ip",
        "IP",
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
        return "IP"
    
    # @preprocess_arg
    # def execute(self, target: str) -> Dict[str, Union[List[str], nx.DiGraph]]:
    def execute(self, target, args):
        """Perform a traceroute to the target and construct a network graph."""
        try:
            print(f"Performing traceroute for {target}...")
            result = subprocess.run(
                ["tracert", target],  # Use "traceroute" instead of "tracert" on Linux
                capture_output=True,
                text=True
            )
            
            output_lines = result.stdout.splitlines()
            previous_hop = target

            # Improved regex for extracting IPv4 and IPv6 addresses
            hop_regex = re.compile(r"(\d+\.\d+\.\d+\.\d+|\b[0-9a-fA-F:]+:[0-9a-fA-F:]+\b)")  

            for line in output_lines:
                matches = hop_regex.findall(line)  # Get all possible IPs in the line
                if matches:
                    for hop in matches:
                        self.graph_manager.add_node(hop, class_type=self.output_class(), datasource=self.metadata_type())  # Add node to the graph

                        if previous_hop:
                            self.graph_manager.add_edge(previous_hop, hop, relationship=self.metadata_type())  # Create edge

                        previous_hop = hop  # Update previous hop for next iteration

        # except Exception as e:
        #     print(f"Error executing traceroute: {e}")
            self.graph_manager.database.set_metadata(target, self.metadata_type(), "RAW", json.dumps(output_lines))
            self.graph_manager.update_node(target, {"traceroute":output_lines})
        except Exception as e:
            print(f"Error during traceroute for {target}: {e}")
        # return (nx.DiGraph())
