"""

Crawls websites for connected pages

"""
import sys
import os
import json
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Vera.Toolchain.plugin_manager import PluginBase
from Vera.Toolchain.common.common import plot

import requests
from bs4 import BeautifulSoup
import time
import urllib.parse
import xml.etree.ElementTree as ET

class spider(PluginBase):

    @staticmethod
    def class_types():
        return [
            "ip",
            "IP",
            "domain",
            "subdomain",
        ]

    @staticmethod
    def description():
        return ""

    @staticmethod
    def output_class():
        return ["ip", "domain"]
    
    @staticmethod
    def metadata_type():
            return("url")
    
    def execute(self, base_url, args):
        found_paths = self.discover_paths(base_url)
        
        # Output the discovered paths to a CSV file
        with open('Reports/found_paths.csv', 'w') as file:
            file.write("Path\n")
            for path in found_paths:
                file.write(f"{path}\n")
        
        print(f"Found paths saved to 'found_paths.csv'")
        self.graph_manager.update_node(base_url, {"spider":found_paths})
        return found_paths

    # Wordlist for fuzzing paths (you can use bigger wordlists from SecLists)
    WORDLIST = ['admin', 'login', 'uploads', 'config', 'images', 'api', 'private']

    # Function to parse a sitemap for paths
    def parse_sitemap(self, url):
        found_paths = []
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise exception for bad response status
            root = ET.fromstring(response.text)
            for child in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
                loc = child.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc").text
                if loc:
                    print(f"Found in sitemap: {loc}")
                    found_paths.append(loc)
        except (requests.RequestException, ET.ParseError) as e:
            print(f"Error parsing sitemap: {e}")
        return found_paths

    # Function to crawl the website to find paths
    def crawl_site(self, base_url):
        found_paths = []
        visited = set()
        to_visit = [base_url if base_url.startswith("http://") else f"http://{base_url}"]
        
        while to_visit:
            url = to_visit.pop()
            if url in visited:
                continue
            
            print(f"Crawling {url}")
            visited.add(url)
            try:
                response = requests.get(url)
                response.raise_for_status()  # Raise exception for bad response status
                found_paths.append(url)
                soup = BeautifulSoup(response.text, 'html.parser')
                for link in soup.find_all('a', href=True):
                    full_url = urllib.parse.urljoin(url, link['href'])
                    if full_url.startswith("http://") and base_url in full_url and full_url not in visited:
                        to_visit.append(full_url)
                        self.graph_manager.add_node(full_url, class_type="domain")
                        self.graph_manager.add_edge(url, full_url)
                    elif not full_url.startswith("http://") and base_url in full_url and full_url not in visited:
                        to_visit.append(f"http://{full_url}")
                        self.graph_manager.add_node(f"http://{full_url}", class_type="domain")
                        self.graph_manager.add_edge(url, f"http://{full_url}")
                time.sleep(1)  # Avoid hitting the server too fast
            except requests.RequestException as e:
                print(f"Request failed for {url}: {e}")
                continue
        
        self.graph_manager.database.set_metadata(base_url, self.metadata_type(), "RAW", json.dumps(found_paths))
        self.graph_manager.update_node(base_url, found_paths)
        return found_paths

    # Function to perform brute-force path discovery (using subdomains)
    def brute_force_paths(self, base_url, subdomains):
        found_paths = []
        for subdomain in subdomains:
            url = f"{subdomain}.{base_url}"
            paths = self.fuzz_paths(url, self.WORDLIST)
            found_paths.extend(paths)
        return found_paths

    # Combine all techniques for path discovery
    def discover_paths(self, base_url):
        all_paths = []
        base_url = f"http://{base_url}"
        
        # Parse the sitemap
        print(f"Parsing sitemap for {base_url}")
        sitemap_url = urllib.parse.urljoin(base_url, "sitemap.xml")
        all_paths.extend(self.parse_sitemap(sitemap_url))

        # Crawl the site
        print(f"Starting crawl on {base_url}")
        all_paths.extend(self.crawl_site(base_url))

        return list(set(all_paths))  # Remove duplicates

# Main function to run the script
if __name__ == "__main__":
    s = Spider()
    base_url = s.BASE_URL  # Change to the target domain
    found_paths = s.discover_paths(base_url)
    
    # Output the discovered paths to a CSV file
    with open('Reports/found_paths.csv', 'w') as file:
        file.write("Path\n")
        for path in found_paths:
            file.write(f"{path}\n")
    
    print(f"Found paths saved to 'found_paths.csv'")
