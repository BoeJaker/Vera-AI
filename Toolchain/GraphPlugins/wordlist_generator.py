import networkx as nx

def extract_wordlist(graph, attribute='class_type', target_values=None):
    """
    Extract node names based on specific attribute values from a NetworkX graph.
    
    :param graph: NetworkX graph object
    :param attribute: Node attribute to filter on (default: 'class_type')
    :param target_values: List of values to include (None returns all)
    :return: List of node names matching the criteria
    """
    target_values = target_values or []
    wordlist = []
    
    for node in graph.nodes():
        node_value = graph.nodes[node].get(attribute)
        
        if not target_values or node_value in target_values:
            # Convert to string in case nodes aren't native strings
            wordlist.append(str(node))
            
    return wordlist

def save_wordlist(wordlist, filename, unique=True, sort=True):
    """
    Save a wordlist to file with options for deduplication and sorting
    
    :param wordlist: List of entries to save
    :param filename: Output filename
    :param unique: Remove duplicates (default: True)
    :param sort: Sort entries alphabetically (default: True)
    """
    processed = wordlist.copy()
    
    if unique:
        processed = list(set(processed))
        
    if sort:
        processed = sorted(processed)
    
    with open(filename, 'w') as f:
        for item in processed:
            f.write(f"{item}\n")

# Example usage
if __name__ == "__main__":
    # Load your graph (replace with actual loading code)
    # G = nx.read_graphml("network_data.graphml")
    G = nx.DiGraph()
    
    # Add example nodes with attributes
    G.add_node("example.com", class_type="domain")
    G.add_node("sub.example.com", class_type="subdomain")
    G.add_node("evil.com", class_type="domain")
    G.add_node("192.168.1.1", class_type="ip")

    # Extract subdomains/domains
    domain_words = extract_wordlist(
        G,
        attribute='class_type',
        target_values=['domain', 'subdomain']
    )
    save_wordlist(domain_words, "domain_wordlist.txt")

    # Example for other extraction (IP addresses)
    ip_addresses = extract_wordlist(
        G,
        attribute='class_type',
        target_values=['ip']
    )
    save_wordlist(ip_addresses, "ip_wordlist.txt")

    # Extract everything (no target values)
    all_nodes = extract_wordlist(G)
    save_wordlist(all_nodes, "all_nodes.txt")
    