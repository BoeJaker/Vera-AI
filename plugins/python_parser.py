"""

Parses Python files into a networkx graph of their component functions and variables

"""
import sys
import os
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from plugin_manager import PluginBase
from common.common import plot

import ast
import networkx as nx

def code_to_networkx(code):
    graph = nx.DiGraph()

    # Parse the code into an Abstract Syntax Tree (AST)
    tree = ast.parse(code)

    # Define a visitor to traverse the AST and build the graph
    class CodeVisitor(ast.NodeVisitor):
        def __init__(self):
            self.current_node = None

        def visit_FunctionDef(self, node):
            function_name = node.name
            graph.add_node(function_name, type='function')
            if self.current_node:
                graph.add_edge(self.current_node, function_name)
            self.current_node = function_name
            self.generic_visit(node)
            self.current_node = None

        def visit_ClassDef(self, node):
            class_name = node.name
            graph.add_node(class_name, type='class')
            if self.current_node:
                graph.add_edge(self.current_node, class_name)
            self.current_node = class_name
            self.generic_visit(node)
            self.current_node = None

        def visit_Call(self, node):
            if isinstance(node.func, ast.Attribute):
                caller = node.func.value.id
                callee = node.func.attr
                graph.add_edge(caller, callee)

    # Visit the AST to populate the graph
    visitor = CodeVisitor()
    visitor.visit(tree)

    return graph

# Example usage:
if __name__ == '__main__':
    python_code = """
    class MyClass:
        def my_method(self):
            print('Hello')

    def my_function():
        obj = MyClass()
        obj.my_method()
    """
    graph = code_to_networkx(python_code)
    print("Nodes:", graph.nodes())
    print("Edges:", graph.edges())
