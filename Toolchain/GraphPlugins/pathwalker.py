 
"""

Returns the subfolders and files of a given directory

"""
import sys
import os
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Vera.Toolchain.plugin_manager import PluginBase
from Vera.Toolchain.common.common import plot


class pathWalker(PluginBase):
    @staticmethod
    def class_types():
        return( [
                "IP",
                "file",
                "folder",
                ])
    
    @staticmethod
    def description():
        return("")
    
    @staticmethod
    def output_class():
        return ["folder", "file"]

    def execute(self, base_path, args):
            """
            Converts a folder/file structure into a NetworkX graph.

            Args:
            - base_path (str): The root directory to start the graph creation.

            Returns:
            - graph (networkx.Graph): A graph representation of the folder structure.
            """

            print(f"Adding {base_path} to graph")
            print(f"Raw path from YAML: {repr(base_path)}")
            base_path = os.path.normpath(base_path) 
            expected_path = r'X:\Programming\Cyber Security\Recon-Map\Visualiser_3'
            # Walk through the directory tree
            print(f"base_path == expected_path? {base_path == expected_path}")
            results=[]
            try:
                for root, dirs, files in os.walk(base_path):
                    # Add the root directory as a node
                    self.graph_manager.graph.add_node(root, class_type='folder')

                    # Add directories as child nodes and create edges
                    for dir_name in dirs:
                        dir_path = os.path.join(root, dir_name)
                        print(f"Detected {dir_path}")
                        results.append(dir_path)
                        self.graph_manager.graph.add_node(dir_path, class_type='folder')  # Add subdirectory as a node
                        self.graph_manager.graph.add_edge(root, dir_path)  # Add edge from root to subdirectory

                    # Add files as child nodes and create edges
                    for file_name in files:
                        file_path = os.path.join(root, file_name)
                        print(f"Detected {file_path}")
                        results.append(file_path)
                        self.graph_manager.graph.add_node(file_path, class_type='file')  # Add file as a node
                        self.graph_manager.graph.add_edge(root, file_path)  # Add edge from root to file
            except Exception as e:
                print(f"Error importing file structure{e}")

            self.graph_manager.database.set_metadata(base_path, self.metadata_type(), "RAW", json.dumps(results))
            self.graph_manager.update_node(base_path, results)
            return results
