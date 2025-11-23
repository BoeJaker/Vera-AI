"""

Parses Bash files into a networkx graph of their component functions and variables

"""
import sys
import os
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from plugin_manager import PluginBase
from common.common import plot

import re
import networkx as nx


class BashParser(PluginBase):
    
    @staticmethod
    def class_types():
        return( [
                "command",
                ] )
    
    @staticmethod
    def description():
        return("Parses Bash files into a networkx graph of their component functions and variables")
    
    @staticmethod
    def output_class():
        return "metadata"

    def execute(self, base_path):
        pass

    def shell_to_networkx(script):
        graph = nx.DiGraph()
        function_calls = {}  # Track function definitions
        variable_assignments = {}  # Track variable definitions

        lines = script.splitlines()
        current_function = None

        for line in lines:
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Detect function definitions
            match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\)\s*\{?", line)
            if match:
                current_function = match.group(1)
                graph.add_node(current_function, type="function")
                function_calls[current_function] = []
                continue
            
            # Detect variable assignments
            match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)=(.*)", line)
            if match:
                variable = match.group(1)
                value = match.group(2)
                graph.add_node(variable, type="variable", value=value)
                variable_assignments[variable] = current_function  # Store last assignment
                if current_function:
                    graph.add_edge(current_function, variable, type="assigns")
                continue

            # Detect function calls and command executions
            match = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", line)
            if match:
                for token in match:
                    if token in function_calls:  # Function call
                        graph.add_edge(current_function, token, type="calls")
                    elif token in variable_assignments:  # Variable usage
                        graph.add_edge(variable_assignments[token], current_function, type="uses")
                    else:  # External command
                        graph.add_node(token, type="command")
                        graph.add_edge(current_function, token, type="calls")

        return graph

if __name__ == '__main__':
    
    # Example Shell Script
    shell_script = """
    #!/bin/bash
    echo "Starting script"

    my_function() {
        var1="hello"
        echo "Inside function"
        ls -l
    }

    another_function() {
        echo $var1
        grep "error" logfile
        my_function
    }

    var2="global_var"
    my_function
    another_function
    """

    # Generate Graph
    graph = shell_to_networkx(shell_script)

    # Display Nodes and Edges
    print("Nodes:", graph.nodes(data=True))
    print("Edges:", list(graph.edges(data=True)))
