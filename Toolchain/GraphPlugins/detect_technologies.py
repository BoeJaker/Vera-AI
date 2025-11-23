import sys
import os
import socket
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import json
# import shodan
import nmap  # For Nmap fingerprinting
# import server_fingerprint  # Example server fingerprint library (could be replaced with pyfingerprint or others)

# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from plugin_manager import PluginBase
from common.common import plot
from common.common import convert_datetime


class TechnologyDetectionPlugin(PluginBase):
    def class_types(self):
        return [
            "Port",
            "ip",
            "IP",
            "host"
        ]
    
    def description(self):
        return "Detects technologies running on a specific port and checks for vulnerabilities (CVE)."
    
    @staticmethod
    def output_class():
        return "metadata"

    def get_banner(self, host, port):
        """ Try to grab the banner of the service running on the port """
        try:
            s = socket.socket()
            s.connect((host, port))
            s.settimeout(2)
            banner = s.recv(1024).decode('utf-8').strip()
            return banner
        except Exception as e:
            return None
    
    def get_shodan_info(self, ip):
        """ Get detailed information from Shodan about the given IP """
        try:
            api = shodan.Shodan("YOUR_SHODAN_API_KEY")
            host = api.host(ip)
            return host
        except shodan.APIError as e:
            return None

    def get_wappalyzer_info(self, url):
        """ Get technologies identified by Wappalyzer from the URL """
        api_key = 'YOUR_WAPPALYZER_API_KEY'
        headers = {'X-API-KEY': api_key}
        response = requests.get(f'https://api.wappalyzer.com/v2/lookup/?urls={url}', headers=headers)
        return response.json()

    def get_cve_info(self, technologies):
        """ Check CVEs for the identified technologies """
        cve_data = []
        for tech in technologies:
            response = requests.get(f"https://api.cve.circl.lu/cve/{tech}")
            if response.status_code == 200:
                cve_data.append(response.json())
        return cve_data

    def perform_fingerprint_detection(self, ip, port):
        """ Use Nmap to perform a fingerprinting scan for the host """
        nm = nmap.PortScanner()
        try:
            nm.scan(ip, str(port))
            if nm.all_hosts():
                host = nm.all_hosts()[0]
                if 'hostnames' in nm[host]:
                    return nm[host]['hostnames'], nm[host]['osmatch']
            return None, None
        except Exception as e:
            return None, None

    def execute(self, address, options):
        # Step 1: Perform banner grabbing if not available
        ip = address.split(":")[0]
        port = address.split(":")[1]
        banner = self.get_banner(ip, port)
        if not banner:
            banner = "No banner detected, using alternative methods"

        # Step 2: Collect technologies based on the banner and other information
        technologies = [banner]

        # Step 3: Try Shodan for more detailed service information
        # shodan_info = self.get_shodan_info(ip)
        # if shodan_info:
        #     technologies.append(shodan_info.get("data", {}))

        # Step 4: Try Wappalyzer (for web services, specifically)
        if port in [80, 443]:  # Common HTTP/HTTPS ports
            url = f"http://{ip}:{port}"
            wappalyzer_info = self.get_wappalyzer_info(url)
            if wappalyzer_info:
                technologies.append(wappalyzer_info)

        # Step 5: Perform fingerprinting using Nmap or other libraries
        hostnames, osmatch = self.perform_fingerprint_detection(ip, port)
        if hostnames:
            technologies.append(f"Hostnames: {hostnames}")
        if osmatch:
            technologies.append(f"OS Match: {osmatch}")

        # Step 6: Cross-reference technologies with CVE data
        cve_data = self.get_cve_info(technologies)

        # Prepare the results
        results = {
            "ip": ip,
            "port": port,
            "technologies": technologies,
            "cve_data": cve_data,
            "timestamp": datetime.now().isoformat()
        }

        # Emit the results
        self.socketio.emit("display_results", {"results": json.dumps(results, default=convert_datetime)})
        
        # Save the results to the database
        self.graph_manager.database.set_metadata(ip, "technology_detection", "RAW", json.dumps(results, default=convert_datetime))
        self.graph_manager.update_node(ip, {"technology_detection_data": results})
        
        return ("display_results", {"results": json.dumps(results, default=convert_datetime)})


# Example usage
if __name__ == "__main__":
    plugin = TechnologyDetectionPlugin()
    ip = "192.168.1.1"
    port = 80
    results = plugin.execute(ip, port, {})
    print(results)
