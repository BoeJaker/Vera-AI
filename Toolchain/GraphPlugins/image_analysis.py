"""

Extracts visual components from images 

"""
import sys
import os
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Vera.Toolchain.plugin_manager import PluginBase
from Vera.Toolchain.common.common import plot