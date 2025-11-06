import re
from typing import List, Tuple, Dict, Any, Set

def extract_entities_from_stream(lines: List[str]) -> Tuple[Set[str], List[Tuple[str, str, Dict[str, Any]]]]:
    """
    Parses a stream of communication logs to infer nodes and edges.

    :param lines: A list of log entries (raw text lines).
    :return: A tuple containing a set of nodes and a list of edges.
    """
    nodes = set()
    edges = []
    
    previous_entity = None  # Keeps track of last observed entity

    for line in lines:
        # Normalize: Remove excess spaces, control characters
        clean_line = re.sub(r'\s+', ' ', line.strip())

        # Extract meaningful entities (IP, Redis keys, Commands, Usernames, etc.)
        entities = re.findall(r'[\w\.-]+', clean_line)

        for entity in entities:
            nodes.add(entity)

            # If there's a previous entity, create an edge
            if previous_entity and previous_entity != entity:
                edges.append((previous_entity, entity, {"context": clean_line}))

            previous_entity = entity  # Update for next iteration

    return nodes, edges


def stream_to_graph(protocol_name: str, log_stream: List[str]) -> Dict[str, Any]:
    """
    Converts a stream of unstructured communication logs into a graph.

    :param protocol_name: Name of the protocol (e.g., "Redis", "PCAP").
    :param log_stream: List of raw log lines.
    :return: A structured graph representation.
    """
    nodes, edges = extract_entities_from_stream(log_stream)

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
        "192.168.1.10:443 <- 200 OK"
    ]

    graph = stream_to_graph("Generic Protocol", log_data)

    print("Graph Representation:")
    print(graph)

