import re
from typing import List, Tuple, Dict, Any, Set

def improved_extract_entities_from_stream(lines: List[str]) -> Tuple[Set[str], List[Tuple[str, str, Dict[str, Any]]]]:
    """
    Parses a stream of communication logs to infer nodes and edges.
    This improved version:
      - Detects directional arrows ("->" or "<-") to split each log line.
      - Uses a robust regex to extract tokens (supports IPs, ports, paths, etc.).
      - Creates both a global edge (from the first to the last token) and edges between adjacent tokens.
      - Falls back to sequential pairing if no arrow is present.
    
    :param lines: List of log entries (raw text lines).
    :return: A tuple containing a set of nodes and a list of edges.
    """
    nodes = set()
    edges = []
    
    for line in lines:
        clean_line = line.strip()
        # Check if the line contains directional arrows.
        if "->" in clean_line or "<-" in clean_line:
            # Split while keeping the arrow tokens.
            parts = re.split(r'(\s*->\s*|\s*<-\s*)', clean_line)
            tokens = []
            arrows = []
            for part in parts:
                if '->' in part or '<-' in part:
                    arrows.append(part.strip())
                else:
                    # Extract tokens including characters common in IPs, URLs, or Redis commands.
                    tokens.extend(re.findall(r'[\w\.\-:/]+', part))
            if tokens:
                nodes.update(tokens)
                # Create a global edge from the first token to the last token.
                edges.append((tokens[0], tokens[-1], {"context": clean_line, "arrows": arrows}))
                # Also create edges between each adjacent token.
                for i in range(len(tokens) - 1):
                    edges.append((tokens[i], tokens[i+1], {"context": clean_line, "arrows": arrows}))
        else:
            # Fallback for lines without arrow indicators: use sequential pairing.
            tokens = re.findall(r'[\w\.\-:/]+', clean_line)
            nodes.update(tokens)
            for i in range(len(tokens) - 1):
                edges.append((tokens[i], tokens[i+1], {"context": clean_line}))
    
    return nodes, edges


def improved_stream_to_graph(protocol_name: str, log_stream: List[str]) -> Dict[str, Any]:
    """
    Converts a stream of unstructured communication logs into a graph.
    
    :param protocol_name: Name of the protocol (e.g., "Redis", "PCAP").
    :param log_stream: List of raw log lines.
    :return: A structured dictionary representing the graph.
    """
    nodes, edges = improved_extract_entities_from_stream(log_stream)
    return {
        "protocol": protocol_name,
        "nodes": list(nodes),
        "edges": edges
    }


# Example Usage
if __name__ == "__main__":
    log_data = [
        "127.0.0.1:6379 -> SET key1 value1",
        "127.0.0.1:6379 <- OK",
        "192.168.1.10:443 -> GET /index.html",
        "192.168.1.10:443 <- 200 OK",
        # A line without arrows to show fallback behavior.
        "UserA sent message to UserB"
    ]

    graph = improved_stream_to_graph("Generic Protocol", log_data)
    print("Graph Representation:")
    print(graph)
