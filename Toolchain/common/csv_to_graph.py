import csv
from typing import List, Dict, Any, Tuple

class DataToGraph:
    def __init__(self):
        """
        Initialize the DataToGraph module.
        """
        pass

    def process_csv(self, file_path: str, entity_columns: List[str], edge_columns: Tuple[str, str], property_columns: List[str] = None) -> Dict[str, Any]:
        """
        Convert CSV data into nodes and edges for graph visualization.
        Args:
            file_path (str): Path to the CSV file.
            entity_columns (List[str]): List of column names to be used as unique identifiers for nodes.
            edge_columns (Tuple[str, str]): Pair of column names to define edges (source, target).
            property_columns (List[str]): List of column names to be added as node/edge properties (optional).
        Returns:
            Dict[str, Any]: A dictionary containing nodes and edges.
        """
        nodes = {}
        edges = []

        with open(file_path, 'r') as csvfile:
            reader = csv.DictReader(csvfile)

            for row in reader:
                # Create nodes from entity columns
                for col in entity_columns:
                    if col not in row:
                        continue
                    entity_id = row[col]
                    if entity_id not in nodes:
                        nodes[entity_id] = {
                            "id": entity_id,
                            "label": entity_id,
                            "properties": {}
                        }

                        # Add properties if specified
                        if property_columns:
                            for prop_col in property_columns:
                                if prop_col in row:
                                    nodes[entity_id]["properties"][prop_col] = row[prop_col]

                # Create edges from edge columns
                if edge_columns[0] in row and edge_columns[1] in row:
                    source = row[edge_columns[0]]
                    target = row[edge_columns[1]]

                    if source and target:
                        edge = {
                            "source": source,
                            "target": target,
                            "properties": {}
                        }

                        # Add properties to edges if specified
                        if property_columns:
                            for prop_col in property_columns:
                                if prop_col in row:
                                    edge["properties"][prop_col] = row[prop_col]

                        edges.append(edge)

        return {"nodes": list(nodes.values()), "edges": edges}

    def process_dict_list(self, data: List[Dict[str, Any]], entity_columns: List[str], edge_columns: Tuple[str, str], property_columns: List[str] = None) -> Dict[str, Any]:
        """
        Convert a list of dictionaries into nodes and edges for graph visualization.
        Args:
            data (List[Dict[str, Any]]): List of dictionaries to process.
            entity_columns (List[str]): List of keys to be used as unique identifiers for nodes.
            edge_columns (Tuple[str, str]): Pair of keys to define edges (source, target).
            property_columns (List[str]): List of keys to be added as node/edge properties (optional).
        Returns:
            Dict[str, Any]: A dictionary containing nodes and edges.
        """
        nodes = {}
        edges = []

        for row in data:
            # Create nodes from entity columns
            for col in entity_columns:
                if col not in row:
                    continue
                entity_id = row[col]
                if entity_id not in nodes:
                    nodes[entity_id] = {
                        "id": entity_id,
                        "label": entity_id,
                        "properties": {}
                    }

                    # Add properties if specified
                    if property_columns:
                        for prop_col in property_columns:
                            if prop_col in row:
                                nodes[entity_id]["properties"][prop_col] = row[prop_col]

            # Create edges from edge columns
            if edge_columns[0] in row and edge_columns[1] in row:
                source = row[edge_columns[0]]
                target = row[edge_columns[1]]

                if source and target:
                    edge = {
                        "source": source,
                        "target": target,
                        "properties": {}
                    }

                    # Add properties to edges if specified
                    if property_columns:
                        for prop_col in property_columns:
                            if prop_col in row:
                                edge["properties"][prop_col] = row[prop_col]

                    edges.append(edge)

        return {"nodes": list(nodes.values()), "edges": edges}

    def parse_nmap_results(self, nmap_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Nmap results into nodes and edges for graph visualization.
        Args:
            nmap_results (Dict[str, Any]): The output from an Nmap scan.
        Returns:
            Dict[str, Any]: A dictionary containing nodes and edges.
        """
        nodes = {}
        edges = []

        for host in nmap_results.get('scan', {}):
            # Add host node
            host_node = {
                "id": host,
                "label": host,
                "group": "host",
                "properties": {
                    "state": nmap_results['scan'][host].get('status', {}).get('state', "unknown"),
                    "protocols": list(nmap_results['scan'][host].get('tcp', {}).keys())
                }
            }
            nodes[host] = host_node

            # Add nodes and edges for open ports
            for protocol, ports in nmap_results['scan'][host].items():
                if isinstance(ports, dict):
                    for port, details in ports.items():
                        port_id = f"{host}:{port}/{protocol}"
                        if port_id not in nodes:
                            nodes[port_id] = {
                                "id": port_id,
                                "label": f"{port}/{protocol}",
                                "group": "port",
                                "properties": details
                            }
                        edges.append({
                            "source": host,
                            "target": port_id,
                            "label": "open port",
                        })

        return {"nodes": list(nodes.values()), "edges": edges}

# Example Usage:
if __name__ == "__main__":
    dtg = DataToGraph()
    graph_data = dtg.process_csv("data.csv", ["Source", "Destination"], ("Source", "Destination"), ["Protocol", "Size"])
    print(graph_data)
