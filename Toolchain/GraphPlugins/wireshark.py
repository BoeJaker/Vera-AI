"""

Parses wireshark data into a networkx graph

"""
import sys
import os
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Vera.Toolchain.plugin_manager import PluginBase
from Vera.Toolchain.common.common import plot

import sqlite3
import pyshark
import networkx as nx
import matplotlib.pyplot as plt


class PacketMonitor(PluginBase):
        
    # @staticmethod
    def class_types(self):
        return( [
            "ip",
            "IP",
            "netblock",
            "domain",
            "subdomain",
            "ip6"
            ] )
    
    @staticmethod
    def description():
        return("Parses Bash files into a networkx graph of their component functions and variables")
    
    @staticmethod
    def output_class():
        return "metadata"
    def __init__(self, capture_interface='eth0', db_name='packet_data.db'):
        self.capture_interface = capture_interface
        self.db_name = db_name
        self.conn = sqlite3.connect(self.db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # Create necessary tables in SQLite database
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS packets (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                source TEXT,
                destination TEXT,
                protocol TEXT,
                length INTEGER,
                raw_data TEXT
            )
        ''')
        self.conn.commit()

    def capture_packets(self, packet_count=100):
        # Capture packets using Wireshark (via pyshark)
        capture = pyshark.LiveCapture(interface=self.capture_interface, bpf_filter='tcp')
        captured_packets = capture.sniff_continuously(packet_count=packet_count)

        for packet in captured_packets:
            try:
                timestamp = packet.sniff_time.strftime('%Y-%m-%d %H:%M:%S')
                source = packet.ip.src
                destination = packet.ip.dst
                protocol = packet.transport_layer
                length = packet.length
                raw_data = str(packet)

                # Store packet data in SQLite database
                self.cursor.execute('''
                    INSERT INTO packets (timestamp, source, destination, protocol, length, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (timestamp, source, destination, protocol, length, raw_data))
                self.conn.commit()

            except AttributeError as e:
                print(f'Error: {e}')
        
        print(f'Captured {packet_count} packets.')

    def create_network_graph(self):
        # Create a NetworkX graph from stored packet data
        self.cursor.execute('SELECT source, destination FROM packets')
        edges = self.cursor.fetchall()

        G = nx.DiGraph()
        G.add_edges_from(edges)

        # Visualize the network graph
        pos = nx.spring_layout(G)
        nx.draw(G, pos, with_labels=True, node_color='skyblue', edge_color='#909090', node_size=500, font_size=10)
        plt.show()

    def close(self):
        # Close database connection
        self.conn.close()

# Example usage:
if __name__ == '__main__':
    monitor = PacketMonitor()
    monitor.capture_packets(packet_count=50)
    monitor.create_network_graph()
    monitor.close()
