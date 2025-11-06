"""

Brute forces the subdomains of a given url

"""
import sys
import os
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from plugin_manager import PluginBase
from common.common import plot

from common.common import convert_datetime
import dns
import json

class BruteSubdomains(PluginBase):
    
    @staticmethod
    def class_types():
        return( [
            "ip",
            "netblock",
            "domain",
            "subdomain",
            "ip6"
            ])
    
    def execute(self, domain, args):
        """Perform brute-force subdomain discovery."""
        discovered_subdomains = []
        try:
            with open("X:\Programming\Cyber Security\Recon-Map\Visulaiser_3\Wordlists\subdomains.txt", 'r') as file:
                subdomain_list = [line.strip() for line in file if line.strip()][:50]
        except FileNotFoundError:
            print(f"Wordlist file not found.")
            exit(1)

        for subdomain in subdomain_list:
            print(subdomain)
            full_domain = f"{subdomain}.{domain}"
            try:
                dns.resolver.resolve(full_domain, 'A')
                discovered_subdomains.append(full_domain)
                self.graph_manager.update_node(full_domain, {"class_type":"subdomain"})
                self.graph_manager.add_edge(full_domain,domain)
                print(f"Discovered subdomain: {full_domain}")
            except dns.resolver.NXDOMAIN:
                pass
            except dns.resolver.NoAnswer:
                pass
            except dns.exception.DNSException:
                pass

        # for d in discovered_subdomains:
        #     self.graph_manager.update_node(d, {"class_type":"subdomain"})
        #     self.graph_manager.add_edge(d,domain)

        self.socketio.emit("update_graph", self.graph_manager.get_graph_data())
        print(discovered_subdomains)
        # self.graph_manager.database.set_metadata(domain, "brute_subdomains", "RAW", json.dumps(discovered_subdomains, default=convert_datetime))
        return discovered_subdomains
