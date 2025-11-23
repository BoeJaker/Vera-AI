import sys
import os
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from plugin_manager import PluginBase
from common.common import plot

import ast
import networkx as nx
import matplotlib.pyplot as plt

class CFGBuilder(ast.NodeVisitor):
    def __init__(self):
        self.graph = nx.DiGraph()
        self.current_node = "Start"
        self.graph.add_node(self.current_node)

    def add_edge(self, new_node):
        """Adds an edge from the current node to a new node and updates the current node."""
        self.graph.add_node(new_node)
        self.graph.add_edge(self.current_node, new_node)
        self.current_node = new_node

    def visit_FunctionDef(self, node):
        """Handles function definitions and creates a new subgraph for it."""
        func_node = f"Func: {node.name}"
        self.add_edge(func_node)
        self.generic_visit(node)

    def visit_If(self, node):
        """Handles if-statements, adding branches to the graph."""
        cond_node = f"If: {ast.unparse(node.test)}"
        self.add_edge(cond_node)

        # Process the "then" branch
        then_branch = f"Then: {ast.unparse(node.test)}"
        self.graph.add_edge(cond_node, then_branch)
        self.current_node = then_branch
        for stmt in node.body:
            self.visit(stmt)

        # Process the "else" branch if it exists
        if node.orelse:
            else_branch = f"Else: {ast.unparse(node.test)}"
            self.graph.add_edge(cond_node, else_branch)
            self.current_node = else_branch
            for stmt in node.orelse:
                self.visit(stmt)

    def visit_For(self, node):
        """Handles for-loops in the execution flow."""
        loop_node = f"For: {ast.unparse(node.target)} in {ast.unparse(node.iter)}"
        self.add_edge(loop_node)
        self.current_node = loop_node
        for stmt in node.body:
            self.visit(stmt)
        self.current_node = loop_node  # Loops back

    def visit_While(self, node):
        """Handles while-loops in the execution flow."""
        loop_node = f"While: {ast.unparse(node.test)}"
        self.add_edge(loop_node)
        self.current_node = loop_node
        for stmt in node.body:
            self.visit(stmt)
        self.current_node = loop_node  # Loops back

    def visit_Expr(self, node):
        """Handles expression statements."""
        expr_node = f"Expr: {ast.unparse(node)}"
        self.add_edge(expr_node)

    def visit_Return(self, node):
        """Handles return statements."""
        return_node = f"Return: {ast.unparse(node.value)}"
        self.add_edge(return_node)

def build_cfg(source_code):
    """Builds a control flow graph (CFG) from Python source code."""
    tree = ast.parse(source_code)
    cfg = CFGBuilder()
    cfg.visit(tree)
    return cfg.graph

def draw_cfg(graph):
    """Draws the control flow graph using networkx and matplotlib."""
    plt.figure(figsize=(10, 6))
    pos = nx.spring_layout(graph)
    nx.draw(graph, pos, with_labels=True, node_color="lightblue", edge_color="gray", node_size=2000, font_size=10)
    plt.show()

if __name__ == '__main__':
        
    # Example Usage:
    code = """
    def example(x):
        if x > 0:
            print("Positive")
        else:
            print("Non-positive")
        for i in range(5):
            print(i)
        return x
    """

    cfg_graph = build_cfg(code)
    draw_cfg(cfg_graph)
