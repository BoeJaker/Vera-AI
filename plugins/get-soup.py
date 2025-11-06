"""

Returns the soup of a given url

"""
import sys
import os
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from plugin_manager import PluginBase
from common.common import plot

from bs4 import BeautifulSoup
import requests

class get_soup(PluginBase):
    @staticmethod
    def class_types():
        return( [
                "ip",
                "domain",
                "subdomain",
                "ip6",
                "Port"
                ])
    
    # @preprocess_arg
    def execute(self, url, args):
        try:
            response = requests.get(f"https://{url}", proxies=self.proxies)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser').prettify()
        except:
            response = requests.get(f"http://{url}", proxies=self.proxies)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser').prettify()        

        return soup