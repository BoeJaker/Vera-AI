"""

Opens a web browser page using the given url

"""
import sys
import os
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from plugin_manager import PluginBase
from common.common import plot
import webbrowser

chrome_path = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
webbrowser.register('chrome', None,webbrowser.BackgroundBrowser(chrome_path))

class open_webpage(PluginBase):

    @staticmethod
    def class_types():
        return( [
            "ip",
            "IP",
            "domain",
            "subdomain"
            ])
        
    @staticmethod
    def description():
        return("")
    
    @staticmethod
    def output_class():
        return ["metadata"]

    def execute(self, address, args):
            webbrowser.get('chrome').open(address, new=2)