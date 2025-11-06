"""

"""

import sys
import os
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from plugin_manager import PluginBase
from common.common import plot

from bs4 import BeautifulSoup
import requests

class get_text(PluginBase):
    @staticmethod
    def class_types():
        return [
            "ip",
            "netblock",
            "domain",
            "subdomain",
            "ip6",
            "Port"
        ]
    @staticmethod
    def description(self):
        return("")
    
    @staticmethod
    def output_class():
        return("text")
    
    def execute(self, url, args):
        print(url)
        try:
            response = requests.get(f"https://{url}", proxies=self.proxies)
            print(response)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                print(soup)
                text = soup.get_text()
                self.graph_manager.update_node(url, {"html_text":text}) # :{"data":text, "metadata_type":self.output_class()}
                print(text)
                return text
            else:
                return f"Failed to retrieve content from {url}. Status code: {response.status_code}"
        
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            raise