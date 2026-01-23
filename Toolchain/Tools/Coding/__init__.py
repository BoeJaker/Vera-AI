# """
# Vera OSINT Toolkit

# Comprehensive Open Source Intelligence tools for network reconnaissance,
# vulnerability assessment, and security analysis.

# Modules:
# - osint_toolkit: Core scanning and detection engines
# - loader: LangChain tool integration

# Features:
# - Network scanning (nmap)
# - DNS enumeration
# - Web technology detection
# - CVE/vulnerability mapping
# - Shodan integration
# - SSL/TLS analysis
# - Neo4j graph storage
# - Automated result export

# Installation:
#     pip install python-nmap dnspython python-whois shodan requests beautifulsoup4
#     sudo apt-get install nmap

# Quick Start:
#     from Vera.Toolchain.Tools.OSINT.loader import add_all_osint_tools
    
#     def ToolLoader(agent):
#         tool_list = []
#         add_all_osint_tools(tool_list, agent)
#         return tool_list
# """

# from .osint_toolkit import (
#     NetworkScanner,
#     DNSRecon,
#     WebTechDetector,
#     CVEMapper,
#     ShodanClient,
#     SSLAnalyzer,
#     Host,
#     Service,
#     Vulnerability,
#     WebTechnology,
#     Domain,
#     export_to_json,
#     export_to_markdown,
#     NMAP_AVAILABLE,
#     DNS_AVAILABLE,
#     WHOIS_AVAILABLE,
#     SHODAN_AVAILABLE
# )

# from .loader import (
#     OSINTTools,
#     add_all_osint_tools,
#     NetworkScanInput,
#     ServiceScanInput,
#     DNSEnumInput,
#     WebTechInput,
#     CVESearchInput,
#     ShodanSearchInput,
#     SSLAnalysisInput,
#     ExportResultsInput
# )

# __all__ = [
#     # Core classes
#     'NetworkScanner',
#     'DNSRecon',
#     'WebTechDetector',
#     'CVEMapper',
#     'ShodanClient',
#     'SSLAnalyzer',
    
#     # Data models
#     'Host',
#     'Service',
#     'Vulnerability',
#     'WebTechnology',
#     'Domain',
    
#     # Integration
#     'OSINTTools',
#     'add_all_osint_tools',
    
#     # Schemas
#     'NetworkScanInput',
#     'ServiceScanInput',
#     'DNSEnumInput',
#     'WebTechInput',
#     'CVESearchInput',
#     'ShodanSearchInput',
#     'SSLAnalysisInput',
#     'ExportResultsInput',
    
#     # Utilities
#     'export_to_json',
#     'export_to_markdown',
    
#     # Feature flags
#     'NMAP_AVAILABLE',
#     'DNS_AVAILABLE',
#     'WHOIS_AVAILABLE',
#     'SHODAN_AVAILABLE'
# ]

# __version__ = '1.0.0'
# __author__ = 'Vera AI'