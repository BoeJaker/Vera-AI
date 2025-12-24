"""

Returns the DNS records of a given url

"""
import sys
import os
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from Vera.Toolchain.plugin_manager import PluginBase
from Vera.Toolchain.common.common import plot

from typing import List, Dict, Union
import dns.resolver

class get_all_dns_records(PluginBase):
    
    @staticmethod
    def class_types():
        return( [
            "ip",
            "netblock",
            "domain",
            "subdomain",
            "ip6"
            ])
    
    # @preprocess_arg
    def execute(self, domain: str, args) -> Dict[str, List[str]]:
        """Retrieve all DNS records for a given domain."""
        record_types = ['A', 'AAAA', 'CNAME', 'MX', 'NS', 'TXT', 'SOA', 'SRV', 'PTR']
        records = {}

        for record_type in record_types:
            try:
                answers = dns.resolver.resolve(domain, record_type)
                records[record_type] = [answer.to_text() for answer in answers]
            except dns.resolver.NoAnswer:
                records[record_type] = []
            except dns.resolver.NXDOMAIN:
                print(f"Domain {domain} does not exist.")
                return {}
            except dns.exception.DNSException as e:
                print(f"Error fetching {record_type} records for {domain}: {e}")
                records[record_type] = []

        return records