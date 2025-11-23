"""
Scans a network or host using nmap and parses the results to a networkx graph
"""
import sys
import os
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from plugin_manager import PluginBase
from common.common import plot
from common.common import convert_datetime
import nmap
import time
import json


class NmapScanner(PluginBase):
    # Applicable class types
    @staticmethod
    def class_types():
        return( [
                "ip",
                "IP",
                "port",
                "netblock",
                "domain",
                "subdomain",
                "ip6"
                ])

    def __init__(self, graph_manager, socketio, args):
        """
        Initialize the NmapScanner
        """
        super().__init__(graph_manager, socketio, args) 
        self.nm = nmap.PortScanner()
    
    def form():
        return({
            'title': 'User Registration',
            'fields': [
                {'name': 'target', 'type': 'text', 'label': 'Target'},
                {'name': 'options', 'type': 'text', 'label': 'Options'},
            ]
        })

 
    def execute(self, target, options):
        self.target = target
        self.options = options
        # Run the scan asynchronously
        # socketio.start_background_task(scanner.run_scan, target, options)
        self.results = self.run_scan(target=self.target, options=self.options)
        print(self.results)
        self.r=self.parse_results_to_graph(self.target)
        print(self.r)
        self.graph_manager.append_graph_data(self.r)
        # self.socketio.emit("update_graph", self.graph_manager.get_graph_data())
        self.graph_manager.database.set_metadata(self.target, "nmap", "RAW", json.dumps(self.results, default=convert_datetime))
        self.graph_manager.update_node(self.target, {"nmap":self.results})
        return(self.graph_manager.get_graph_data())

    def run_scan(self, target: str, options: str = "-sS"):
        """
        Run an Nmap scan and broadcast the results to the front-end.
        Args:
            target (str): The IP address or domain to scan.
            options (str): Nmap options (default is SYN scan).
        """
        print(f"Running Nmap scan on {target} with options '{options}'...")
        try:
            self.nm.scan(hosts=target, arguments=options+" -e eth4")
            graph_data = self.parse_results_to_graph(target)
            # plot(graph_data)
            self.broadcast_graph_data(graph_data)
        except Exception as e:
            print(f"Error running Nmap scan: {e}")
        # return(graph_data)

    def parse_results_to_graph(self, target: str):
        source = target
        """
        Parse Nmap results into D3-compatible graph data (nodes and links).
        Args:
            target (str): The target of the scan.
        Returns:
            dict: D3 graph data with `nodes` and `links`.
        """
        nodes = []
        links = []

        for host in self.nm.all_hosts():
            print(f"Processing host: {host}")
            host_node = {
                "id": host,
                "group": 1,  # Group can indicate different types of hosts, e.g., router, client, etc.
                "class_type": "IP",
                "properties": {
                    "state": self.nm[host].state(),
                    "addresses": self.nm[host].hostname(),
                    "protocols": self.nm[host].all_protocols(),
                }
            }
            links.append({
                        "source": source,
                        "target": f"{host}"  # e.g., "192.168.1.1:80"
                        # "label": f"{protocol}"
                        # "properties": {
                        #     "state": self.nm[host][protocol][port]['state']
                        # }
                    })
            nodes.append(host_node)

            # Add links for open ports
            for protocol in self.nm[host].all_protocols():
                ports = self.nm[host][protocol].keys()
                for port in ports:
                    nodes.append({
                        "id": f"{host}:{port}",
                        "group": 2,  # Group can indicate different types of hosts, e.g., router, client, etc.
                        "class_type": "Port", 
                        "properties": {
                        "state": self.nm[host][protocol][port]['state'],
                        "addresses": f"{protocol}:{port}",
                        "protocols": self.nm[host].all_protocols(),
                        }
                    })
                    links.append({
                        "source": host,
                        "target": f"{host}:{port}",  # e.g., "192.168.1.1:80"
                        # "label": f"{protocol}:{port}"
                        # "properties": {
                        #     "state": self.nm[host][protocol][port]['state']
                        # }
                    })

        return {"nodes": nodes, "links": links}

    def continuous_scan(self, target: str, interval: int = 60, options: str = "-sS"):
        """
        Run Nmap scans continuously at a fixed interval and broadcast updates.
        Args:
            target (str): The IP address or domain to scan.
            interval (int): Interval between scans in seconds.
            options (str): Nmap options.
        """
        while True:
            self.run_scan(target, options)
            print(f"Waiting for {interval} seconds before the next scan...")
            time.sleep(interval)

if __name__ == "__main__":

    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your_secret_key'
    socketio = SocketIO(app, cors_allowed_origins="*")


    scanner = NmapScanner()
    scanner.run_scan(target="192.168.1.1", options="")