 
"""

Opens a file using the default program

"""
import sys
import os
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Vera.Toolchain.plugin_manager import PluginBase
from Vera.Toolchain.common.common import plot

class openFile(PluginBase):
    
    @staticmethod
    def class_types():
        return( [
                "file",
                "folder",
                ])
        
    @staticmethod
    def description():
        return("")
    
    @staticmethod
    def output_class():
        return "file"

    def execute(self, filepath):
        pass
