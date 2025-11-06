import subprocess
import time
import re
import networkx as nx
import matplotlib.pyplot as plt

def get_http_modules():
    """Retrieves all auxiliary scanner modules related to HTTP in Metasploit."""
    msf_command = "msfconsole -q -x 'show auxiliary' | grep http"
    try:
        result = subprocess.run(msf_command, shell=True, capture_output=True, text=True)
        modules = [line.split()[0] for line in result.stdout.splitlines() if line.startswith('auxiliary/')]
        return modules
    except Exception as e:
        print(f"Error retrieving Metasploit modules: {str(e)}")
        return []

def run_metasploit_module(url, module):
    """Runs a Metasploit module against the given URL."""
    print(f"\n[+] Running {module} on {url}...\n")
    msf_command = f"""msfconsole -q -x '
    use {module};
    set RHOSTS {url};
    run;
    exit'"""

    try:
        result = subprocess.run(msf_command, shell=True, capture_output=True, text=True, timeout=120)
        
        # Save results to a log file
        with open("metasploit_scan_results.txt", "a") as log_file:
            log_file.write(f"\n===== {module} =====\n")
            log_file.write(result.stdout + "\n")
        
        print(f"[✔] {module} completed. Results saved.\n")
    except subprocess.TimeoutExpired:
        print(f"[!] {module} timed out.\n")
    except Exception as e:
        print(f"[X] Error running {module}: {str(e)}\n")

def parse_results(file_path):
    """
    Parses the Metasploit scan results and extracts entities (IPs, URLs, services).
    Returns a list of (node1, node2) relationships.
    """
    relationships = set()

    with open(file_path, "r") as file:
        data = file.readlines()
    
    current_module = None
    for line in data:
        line = line.strip()

        # Identify module sections
        if line.startswith("====="):
            current_module = line.replace("=====", "").strip()
            continue
        
        # Extract entities (IP, domains, services, directories)
        ip_match = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", line)
        url_match = re.findall(r"https?://[^\s]+", line)
        directory_match = re.findall(r"/[a-zA-Z0-9_-]+/?", line)

        # Create relationships
        if ip_match:
            for ip in ip_match:
                relationships.add(("Target", ip))  # Connect target to IP
            
        if url_match:
            for url in url_match:
                relationships.add(("Target", url))
                if current_module:
                    relationships.add((url, current_module))  # Link URLs to modules
        
        if directory_match:
            for directory in directory_match:
                relationships.add(("Web Server", directory))  # Link discovered directories

    return list(relationships)

def create_graph(relationships):
    """Generates a network graph from extracted relationships."""
    G = nx.Graph()

    for node1, node2 in relationships:
        G.add_edge(node1, node2)

    plt.figure(figsize=(10, 7))
    pos = nx.spring_layout(G)
    nx.draw(G, pos, with_labels=True, node_color="lightblue", edge_color="gray", node_size=2000, font_size=10)
    plt.title("Metasploit Scan Entity Relationship Graph")
    plt.show()

def main():
    """Main function to fetch HTTP modules, run scans, and visualize results."""
    url = input("Enter the target URL/IP: ").strip()

    print("\n[!] Fetching available Metasploit HTTP modules...")
    http_modules = get_http_modules()
    
    if not http_modules:
        print("[X] No HTTP modules found.")
        return

    print(f"[+] Found {len(http_modules)} HTTP-related modules.\n")

    for module in http_modules:
        run_metasploit_module(url, module)
        time.sleep(3)  # Small delay to avoid overwhelming the system

    print("[✅] Scan completed. Processing results...\n")

    relationships = parse_results("metasploit_scan_results.txt")
    
    if relationships:
        create_graph(relationships)
        print("[📊] Graph generated successfully.")
    else:
        print("[X] No meaningful data found to visualize.")

if __name__ == "__main__":
    main()
