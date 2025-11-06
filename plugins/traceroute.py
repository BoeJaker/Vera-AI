"""

Returns the route to a given url

"""
import sys
import os
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from plugin_manager import PluginBase
from common.common import plot

from typing import List, Dict, Union
import subprocess

class traceroute(PluginBase):

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
        return "metadata"

    # @preprocess_arg
    # def execute(self, target: str, args) -> List[str]:
    def execute(self, target, args):
        """Perform a traceroute to the target."""
        try:
            print(f"Performing traceroute for {target}...")
            result = subprocess.run(
                ["tracert", target],
                capture_output=True,
                text=True
            )
            
        except Exception as e:
            print(f"Error during traceroute for {target}: {e}")
            return []
        self.graph_manager.database.set_metadata(target, self.metadata_type(), "RAW", json.dumps(result.stdout.splitlines()))
        self.graph_manager.update_node(target, result.stdout.splitlines())
        return result.stdout.splitlines()
