#!/usr/bin/env python3
"""
OSINT Tools Integration for Vera Agent System

Integrates the OSINT toolkit with:
- LangChain tool system
- Neo4j graph memory
- ChromaDB vector storage
- Pydantic schemas for validation

Usage in tools.py:
    from Vera.Toolchain.Tools.OSINT.loader import add_all_osint_tools
    
    def ToolLoader(agent):
        tool_list = [...]
        add_all_osint_tools(tool_list, agent)
        return tool_list
"""

import os
import json
import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain.tools import StructuredTool
import logging

try:
    from Vera.Toolchain.Tools.OSINT.network import (
        NetworkScanner, DNSRecon, WebTechDetector, CVEMapper,
        ShodanClient, SSLAnalyzer, Host, Service, Vulnerability,
        WebTechnology, Domain, export_to_json, export_to_markdown,
        NMAP_AVAILABLE, DNS_AVAILABLE, WHOIS_AVAILABLE, SHODAN_AVAILABLE
    )
except ImportError:
    from Toolchain.Tools.OSINT.network import (
        NetworkScanner, DNSRecon, WebTechDetector, CVEMapper,
        ShodanClient, SSLAnalyzer, Host, Service, Vulnerability,
        WebTechnology, Domain, export_to_json, export_to_markdown,
        NMAP_AVAILABLE, DNS_AVAILABLE, WHOIS_AVAILABLE, SHODAN_AVAILABLE
    )

logger = logging.getLogger(__name__)


# =============================================================================
# PYDANTIC SCHEMAS FOR TOOL INPUTS
# =============================================================================

class NetworkScanInput(BaseModel):
    """Schema for network scanning"""
    target: str = Field(..., description="IP, CIDR, or hostname (e.g., '192.168.1.0/24', 'example.com')")
    ports: str = Field(default="1-1000", description="Port range (e.g., '1-1000', '80,443,8080')")
    scan_type: str = Field(default="normal", description="Scan type: 'quick', 'normal', or 'intensive'")

class ServiceScanInput(BaseModel):
    """Schema for service detection"""
    target: str = Field(..., description="IP or hostname to scan for services")
    ports: str = Field(default="1-1000", description="Port range to scan")

class DNSEnumInput(BaseModel):
    """Schema for DNS enumeration"""
    domain: str = Field(..., description="Target domain (e.g., 'example.com')")
    enumerate_subdomains: bool = Field(default=True, description="Perform subdomain enumeration")
    attempt_zone_transfer: bool = Field(default=False, description="Attempt DNS zone transfer (AXFR)")

class WebTechInput(BaseModel):
    """Schema for web technology detection"""
    url: str = Field(..., description="Target URL (e.g., 'https://example.com')")

class CVESearchInput(BaseModel):
    """Schema for CVE searching"""
    product: str = Field(..., description="Product name (e.g., 'apache', 'wordpress')")
    version: Optional[str] = Field(default=None, description="Specific version (optional)")
    max_results: int = Field(default=10, description="Maximum CVEs to return")

class ShodanSearchInput(BaseModel):
    """Schema for Shodan searches"""
    query: str = Field(..., description="Shodan search query or IP address")
    search_type: str = Field(default="ip", description="Search type: 'ip' or 'query'")
    max_results: int = Field(default=10, description="Maximum results for query search")

class SSLAnalysisInput(BaseModel):
    """Schema for SSL/TLS analysis"""
    hostname: str = Field(..., description="Target hostname")
    port: int = Field(default=443, description="SSL port (default 443)")

class ExportResultsInput(BaseModel):
    """Schema for exporting results"""
    scan_id: str = Field(..., description="ID of scan results to export")
    format: str = Field(default="json", description="Export format: 'json' or 'markdown'")
    output_file: str = Field(..., description="Output file path")


# =============================================================================
# OSINT TOOLS WRAPPER CLASS
# =============================================================================

class OSINTTools:
    """Wrapper for OSINT toolkit with memory integration"""
    
    def __init__(self, agent):
        self.agent = agent
        self.scan_results = {}  # Store scan results by ID
        
        # Initialize toolkit components
        self.network_scanner = NetworkScanner() if NMAP_AVAILABLE else None
        self.dns_recon = DNSRecon() if DNS_AVAILABLE else None
        self.web_detector = WebTechDetector()
        self.cve_mapper = CVEMapper()
        self.ssl_analyzer = SSLAnalyzer()
        
        # Shodan (requires API key)
        shodan_key = os.getenv("SHODAN_API_KEY")
        if shodan_key and SHODAN_AVAILABLE:
            self.shodan_client = ShodanClient(shodan_key)
        else:
            self.shodan_client = None
        
        logger.info("OSINT toolkit initialized")
    
    # -------------------------------------------------------------------------
    # NETWORK SCANNING
    # -------------------------------------------------------------------------
    
    def scan_network(self, target: str, ports: str = "1-1000", 
                    scan_type: str = "normal") -> str:
        """
        Scan network for hosts, ports, and services.
        
        Scan types:
        - 'quick': Fast ping scan for host discovery
        - 'normal': Standard port scan with service detection
        - 'intensive': Deep scan with OS detection and scripts
        
        Results are stored in Neo4j graph and linked to current session.
        
        Args:
            target: IP, CIDR, or hostname
            ports: Port range to scan
            scan_type: Type of scan to perform
        
        Returns:
            Summary of discovered hosts and services
        """
        if not self.network_scanner:
            return "[Error] Network scanning not available. Install: pip install python-nmap && sudo apt-get install nmap"
        
        try:
            scan_id = f"scan_{int(time.time()*1000)}"
            
            # Perform scan based on type
            if scan_type == "quick":
                result = self.network_scanner.quick_scan(target)
                hosts = []
                for h in result.get('hosts', []):
                    hosts.append(Host(
                        ip=h['ip'],
                        hostname=h.get('hostname'),
                        status=h['status']
                    ))
            elif scan_type == "intensive":
                hosts = self.network_scanner.scan_network(
                    target, ports, arguments="-sV -O -A -T4 --script=default"
                )
            else:  # normal
                hosts = self.network_scanner.scan_network(target, ports)
            
            # Store in memory
            self._store_network_scan(scan_id, hosts)
            
            # Store results for export
            self.scan_results[scan_id] = {
                "type": "network_scan",
                "target": target,
                "scan_type": scan_type,
                "timestamp": time.time(),
                "hosts": [self._host_to_dict(h) for h in hosts]
            }
            
            # Generate summary
            output = [f"Network Scan Results (ID: {scan_id})"]
            output.append(f"Target: {target} | Type: {scan_type} | Hosts: {len(hosts)}\n")
            
            for host in hosts:
                output.append(f"📍 {host.ip} ({host.hostname or 'Unknown'})")
                output.append(f"   Status: {host.status}")
                if host.os:
                    output.append(f"   OS: {host.os}")
                if host.open_ports:
                    output.append(f"   Open Ports: {', '.join(map(str, host.open_ports[:20]))}")
                    if len(host.open_ports) > 20:
                        output.append(f"   ... and {len(host.open_ports) - 20} more")
                output.append("")
            
            output.append(f"\n💾 Results stored in graph memory with ID: {scan_id}")
            output.append(f"📤 Export with: export_scan_results(scan_id='{scan_id}', format='json', output_file='scan.json')")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Network scan failed: {e}", exc_info=True)
            return f"[Error] Network scan failed: {str(e)}"
    
    def scan_services(self, target: str, ports: str = "1-1000") -> str:
        """
        Detailed service detection and fingerprinting.
        
        Identifies:
        - Service names and versions
        - Products running on ports
        - Service banners
        - CPE identifiers (for CVE mapping)
        
        Results include automatic CVE mapping for detected services.
        
        Args:
            target: IP or hostname
            ports: Port range to scan
        
        Returns:
            Detailed service information with vulnerabilities
        """
        if not self.network_scanner:
            return "[Error] Service scanning not available. Install python-nmap."
        
        try:
            scan_id = f"service_scan_{int(time.time()*1000)}"
            
            # Scan services
            services = self.network_scanner.scan_services(target, ports)
            
            # Map to CVEs
            all_vulns = []
            for service in services:
                vulns = self.cve_mapper.map_service_to_cves(service)
                service.vulnerabilities = vulns
                all_vulns.extend(vulns)
            
            # Store in memory
            self._store_service_scan(scan_id, target, services)
            
            # Store for export
            self.scan_results[scan_id] = {
                "type": "service_scan",
                "target": target,
                "timestamp": time.time(),
                "services": [self._service_to_dict(s) for s in services],
                "vulnerabilities": [self._vuln_to_dict(v) for v in all_vulns]
            }
            
            # Generate output
            output = [f"Service Scan Results (ID: {scan_id})"]
            output.append(f"Target: {target} | Services: {len(services)}\n")
            
            for service in services:
                output.append(f"🔌 Port {service.port}/{service.protocol}")
                output.append(f"   Service: {service.service}")
                if service.product:
                    output.append(f"   Product: {service.product} {service.version or ''}")
                if service.banner:
                    output.append(f"   Banner: {service.banner[:100]}")
                
                # Show vulnerabilities
                if hasattr(service, 'vulnerabilities') and service.vulnerabilities:
                    output.append(f"   🔴 Vulnerabilities: {len(service.vulnerabilities)}")
                    for vuln in service.vulnerabilities[:3]:
                        severity = vuln.severity or "Unknown"
                        output.append(f"      - {vuln.cve_id} ({severity})")
                output.append("")
            
            # Summary of vulnerabilities
            if all_vulns:
                output.append(f"\n⚠️  Total Vulnerabilities Found: {len(all_vulns)}")
                critical = [v for v in all_vulns if v.severity and "CRITICAL" in v.severity.upper()]
                high = [v for v in all_vulns if v.severity and "HIGH" in v.severity.upper()]
                if critical:
                    output.append(f"   🔴 Critical: {len(critical)}")
                if high:
                    output.append(f"   🟠 High: {len(high)}")
            
            output.append(f"\n💾 Scan ID: {scan_id}")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Service scan failed: {e}", exc_info=True)
            return f"[Error] Service scan failed: {str(e)}"
    
    # -------------------------------------------------------------------------
    # DNS RECONNAISSANCE
    # -------------------------------------------------------------------------
    
    def enumerate_dns(self, domain: str, enumerate_subdomains: bool = True,
                     attempt_zone_transfer: bool = False) -> str:
        """
        Comprehensive DNS reconnaissance.
        
        Gathers:
        - A, NS, MX, TXT records
        - Nameserver information
        - Subdomain enumeration (optional)
        - Zone transfer attempt (optional)
        - WHOIS data
        
        Results stored in graph with domain as central node.
        
        Args:
            domain: Target domain
            enumerate_subdomains: Perform subdomain brute force
            attempt_zone_transfer: Try DNS zone transfer
        
        Returns:
            DNS information and discovered subdomains
        """
        if not self.dns_recon:
            return "[Error] DNS tools not available. Install: pip install dnspython python-whois"
        
        try:
            scan_id = f"dns_enum_{int(time.time()*1000)}"
            
            # Basic DNS enumeration
            domain_info = self.dns_recon.enumerate_dns(domain)
            
            # Subdomain enumeration
            subdomains = []
            if enumerate_subdomains:
                subdomains = self.dns_recon.enumerate_subdomains(domain)
                domain_info.subdomains = subdomains
            
            # Zone transfer
            zone_records = []
            if attempt_zone_transfer:
                zone_records = self.dns_recon.dns_zone_transfer(domain)
                if zone_records:
                    domain_info.subdomains.extend(zone_records)
            
            # Store in memory
            self._store_dns_scan(scan_id, domain_info)
            
            # Store for export
            self.scan_results[scan_id] = {
                "type": "dns_enumeration",
                "domain": domain,
                "timestamp": time.time(),
                "dns_info": self._domain_to_dict(domain_info)
            }
            
            # Generate output
            output = [f"DNS Enumeration Results (ID: {scan_id})"]
            output.append(f"Domain: {domain}\n")
            
            if hasattr(domain_info, 'a_records') and domain_info.a_records:
                output.append(f"📍 A Records:")
                for record in domain_info.a_records:
                    output.append(f"   {record}")
                output.append("")
            
            if domain_info.nameservers:
                output.append(f"🌐 Nameservers:")
                for ns in domain_info.nameservers:
                    output.append(f"   {ns}")
                output.append("")
            
            if domain_info.mx_records:
                output.append(f"📧 MX Records:")
                for mx in domain_info.mx_records:
                    output.append(f"   {mx}")
                output.append("")
            
            if domain_info.txt_records:
                output.append(f"📝 TXT Records:")
                for txt in domain_info.txt_records[:5]:
                    output.append(f"   {txt[:100]}")
                output.append("")
            
            if domain_info.registrar:
                output.append(f"🏢 Registrar: {domain_info.registrar}")
                if domain_info.creation_date:
                    output.append(f"   Created: {domain_info.creation_date}")
                if domain_info.expiration_date:
                    output.append(f"   Expires: {domain_info.expiration_date}")
                output.append("")
            
            if subdomains:
                output.append(f"🔍 Discovered Subdomains ({len(subdomains)}):")
                for sub in subdomains[:20]:
                    output.append(f"   • {sub}")
                if len(subdomains) > 20:
                    output.append(f"   ... and {len(subdomains) - 20} more")
                output.append("")
            
            if zone_records:
                output.append(f"⚠️  Zone Transfer Successful! Found {len(zone_records)} records")
            
            output.append(f"\n💾 Scan ID: {scan_id}")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"DNS enumeration failed: {e}", exc_info=True)
            return f"[Error] DNS enumeration failed: {str(e)}"
    
    # -------------------------------------------------------------------------
    # WEB RECONNAISSANCE
    # -------------------------------------------------------------------------
    
    def detect_web_technologies(self, url: str) -> str:
        """
        Identify technologies used by a website.
        
        Detects:
        - Web frameworks (React, Vue, Angular, etc.)
        - CMS systems (WordPress, Drupal, etc.)
        - JavaScript libraries (jQuery, Bootstrap, etc.)
        - Web servers (nginx, Apache, etc.)
        - Analytics platforms
        - CDNs and hosting
        
        Automatically maps technologies to known CVEs.
        
        Args:
            url: Target URL
        
        Returns:
            List of detected technologies with vulnerabilities
        """
        try:
            scan_id = f"webtech_{int(time.time()*1000)}"
            
            # Detect technologies
            technologies = self.web_detector.detect(url)
            
            # Map to CVEs
            all_vulns = []
            for tech in technologies:
                vulns = self.cve_mapper.map_technology_to_cves(tech)
                tech.vulnerabilities = vulns
                all_vulns.extend(vulns)
            
            # Store in memory
            self._store_webtech_scan(scan_id, url, technologies)
            
            # Store for export
            self.scan_results[scan_id] = {
                "type": "web_technologies",
                "url": url,
                "timestamp": time.time(),
                "technologies": [self._tech_to_dict(t) for t in technologies],
                "vulnerabilities": [self._vuln_to_dict(v) for v in all_vulns]
            }
            
            # Generate output
            output = [f"Web Technology Detection (ID: {scan_id})"]
            output.append(f"URL: {url}\n")
            
            # Group by category
            by_category = {}
            for tech in technologies:
                cat = tech.category
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(tech)
            
            for category, techs in sorted(by_category.items()):
                output.append(f"🛠️  {category}:")
                for tech in techs:
                    conf = f"{tech.confidence:.0%}"
                    ver = f" v{tech.version}" if tech.version else ""
                    output.append(f"   • {tech.name}{ver} ({conf} confidence)")
                    
                    # Show vulnerabilities
                    if hasattr(tech, 'vulnerabilities') and tech.vulnerabilities:
                        output.append(f"     🔴 {len(tech.vulnerabilities)} known vulnerabilities")
                        for vuln in tech.vulnerabilities[:2]:
                            output.append(f"        - {vuln.cve_id}")
                output.append("")
            
            # Summary
            if all_vulns:
                output.append(f"⚠️  Total Vulnerabilities: {len(all_vulns)}")
                critical = [v for v in all_vulns if v.severity and "CRITICAL" in v.severity.upper()]
                if critical:
                    output.append(f"   🔴 {len(critical)} Critical vulnerabilities found!")
            
            output.append(f"\n💾 Scan ID: {scan_id}")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Web tech detection failed: {e}", exc_info=True)
            return f"[Error] Web technology detection failed: {str(e)}"
    
    # -------------------------------------------------------------------------
    # VULNERABILITY MAPPING
    # -------------------------------------------------------------------------
    
    def search_cves(self, product: str, version: Optional[str] = None,
                   max_results: int = 10) -> str:
        """
        Search for CVE vulnerabilities affecting a product.
        
        Uses the National Vulnerability Database (NVD) API.
        
        Args:
            product: Product name (e.g., "apache", "wordpress", "openssh")
            version: Specific version (optional, e.g., "2.4.49")
            max_results: Maximum CVEs to return
        
        Returns:
            List of CVEs with severity, CVSS scores, and descriptions
        """
        try:
            vulns = self.cve_mapper.search_cves(product, version, max_results)
            
            if not vulns:
                return f"No CVEs found for {product} {version or ''}"
            
            # Store in memory
            scan_id = f"cve_search_{int(time.time()*1000)}"
            self._store_cve_search(scan_id, product, version, vulns)
            
            # Generate output
            output = [f"CVE Search Results"]
            output.append(f"Product: {product} {version or '(all versions)'}")
            output.append(f"Found: {len(vulns)} vulnerabilities\n")
            
            for vuln in vulns:
                severity = vuln.severity or "Unknown"
                score = vuln.cvss_score or "N/A"
                
                output.append(f"🔴 {vuln.cve_id} - {severity} (CVSS: {score})")
                output.append(f"   Published: {vuln.published or 'Unknown'}")
                output.append(f"   {vuln.description[:200]}...")
                if vuln.references:
                    output.append(f"   References: {vuln.references[0]}")
                output.append("")
            
            output.append(f"💾 Search ID: {scan_id}")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"CVE search failed: {e}", exc_info=True)
            return f"[Error] CVE search failed: {str(e)}"
    
    # -------------------------------------------------------------------------
    # SHODAN INTEGRATION
    # -------------------------------------------------------------------------
    
    def shodan_search(self, query: str, search_type: str = "ip",
                     max_results: int = 10) -> str:
        """
        Search Shodan for hosts and services.
        
        Requires SHODAN_API_KEY environment variable.
        
        Search types:
        - 'ip': Lookup specific IP address
        - 'query': Search using Shodan query syntax
        
        Examples:
        - IP lookup: query="8.8.8.8", search_type="ip"
        - Service search: query="apache port:80", search_type="query"
        - Product search: query="product:MySQL", search_type="query"
        
        Args:
            query: IP address or Shodan query
            search_type: Type of search ('ip' or 'query')
            max_results: Max results for query searches
        
        Returns:
            Host information from Shodan database
        """
        if not self.shodan_client:
            return "[Error] Shodan not available. Set SHODAN_API_KEY environment variable."
        
        try:
            scan_id = f"shodan_{int(time.time()*1000)}"
            
            if search_type == "ip":
                result = self.shodan_client.search_host(query)
                
                if not result:
                    return f"No Shodan data found for {query}"
                
                output = [f"Shodan Results for {query}"]
                output.append(f"Organization: {result.get('org', 'Unknown')}")
                output.append(f"OS: {result.get('os', 'Unknown')}")
                output.append(f"Hostnames: {', '.join(result.get('hostnames', []))}")
                output.append(f"\nOpen Ports: {', '.join(map(str, result.get('ports', [])))}")
                
                if result.get('vulns'):
                    output.append(f"\n🔴 Known Vulnerabilities: {len(result['vulns'])}")
                    for vuln in list(result['vulns'])[:5]:
                        output.append(f"   • {vuln}")
                
                if result.get('services'):
                    output.append(f"\n🔌 Services:")
                    for svc in result['services'][:10]:
                        output.append(f"   Port {svc['port']}: {svc.get('product', 'Unknown')}")
                
                # Store
                self._store_shodan_result(scan_id, query, result)
                
            else:  # query search
                results = self.shodan_client.search_query(query, max_results)
                
                if not results:
                    return f"No results found for query: {query}"
                
                output = [f"Shodan Search Results"]
                output.append(f"Query: {query}")
                output.append(f"Results: {len(results)}\n")
                
                for i, host in enumerate(results, 1):
                    output.append(f"{i}. {host['ip']}")
                    output.append(f"   Port: {host.get('port', 'N/A')}")
                    output.append(f"   Product: {host.get('product', 'Unknown')}")
                    output.append(f"   Organization: {host.get('org', 'Unknown')}")
                    if host.get('hostnames'):
                        output.append(f"   Hostnames: {', '.join(host['hostnames'])}")
                    output.append("")
                
                # Store
                self._store_shodan_results(scan_id, query, results)
            
            output.append(f"\n💾 Scan ID: {scan_id}")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Shodan search failed: {e}", exc_info=True)
            return f"[Error] Shodan search failed: {str(e)}"
    
    # -------------------------------------------------------------------------
    # SSL/TLS ANALYSIS
    # -------------------------------------------------------------------------
    
    def analyze_ssl(self, hostname: str, port: int = 443) -> str:
        """
        Analyze SSL/TLS certificate and configuration.
        
        Checks:
        - Certificate validity and expiration
        - Issuer and subject information
        - Protocol versions (checks for weak protocols)
        - Cipher suites (checks for weak ciphers)
        - Common SSL/TLS vulnerabilities
        
        Args:
            hostname: Target hostname
            port: SSL port (default 443)
        
        Returns:
            Certificate info and security assessment
        """
        try:
            scan_id = f"ssl_scan_{int(time.time()*1000)}"
            
            result = self.ssl_analyzer.analyze_ssl(hostname, port)
            
            if 'error' in result:
                return f"[Error] SSL analysis failed: {result['error']}"
            
            # Store in memory
            self._store_ssl_scan(scan_id, hostname, result)
            
            # Generate output
            output = [f"SSL/TLS Analysis (ID: {scan_id})"]
            output.append(f"Target: {hostname}:{port}\n")
            
            cert = result.get('certificate', {})
            if cert:
                subject = cert.get('subject', {})
                issuer = cert.get('issuer', {})
                
                output.append(f"📜 Certificate:")
                output.append(f"   Subject: {subject.get('commonName', 'Unknown')}")
                output.append(f"   Issuer: {issuer.get('commonName', 'Unknown')}")
                output.append(f"   Valid From: {cert.get('notBefore', 'Unknown')}")
                output.append(f"   Valid Until: {cert.get('notAfter', 'Unknown')}")
                output.append("")
            
            protocols = result.get('protocol_versions', [])
            if protocols:
                output.append(f"🔐 Protocol: {', '.join(protocols)}")
                output.append("")
            
            ciphers = result.get('ciphers', [])
            if ciphers:
                output.append(f"🔑 Cipher Suites:")
                for cipher in ciphers[:5]:
                    output.append(f"   • {cipher.get('name')} ({cipher.get('bits')} bits)")
                output.append("")
            
            issues = result.get('issues', [])
            if issues:
                output.append(f"⚠️  Security Issues:")
                for issue in issues:
                    output.append(f"   🔴 {issue}")
            else:
                output.append(f"✅ No obvious security issues detected")
            
            output.append(f"\n💾 Scan ID: {scan_id}")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"SSL analysis failed: {e}", exc_info=True)
            return f"[Error] SSL analysis failed: {str(e)}"
    
    # -------------------------------------------------------------------------
    # RESULT EXPORT
    # -------------------------------------------------------------------------
    
    def export_scan_results(self, scan_id: str, format: str = "json",
                          output_file: str = None) -> str:
        """
        Export scan results to file.
        
        Formats:
        - 'json': Structured JSON data
        - 'markdown': Human-readable report
        
        Args:
            scan_id: ID of scan to export
            format: Export format
            output_file: Output file path
        
        Returns:
            Export status message
        """
        if scan_id not in self.scan_results:
            return f"[Error] No scan results found with ID: {scan_id}"
        
        if not output_file:
            timestamp = int(time.time())
            output_file = f"osint_scan_{scan_id}_{timestamp}.{format}"
        
        try:
            data = self.scan_results[scan_id]
            
            if format == "json":
                export_to_json(data, output_file)
            elif format == "markdown":
                export_to_markdown(data, output_file)
            else:
                return f"[Error] Unsupported format: {format}"
            
            return f"✅ Results exported to: {output_file}"
            
        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=True)
            return f"[Error] Export failed: {str(e)}"
    
    # -------------------------------------------------------------------------
    # MEMORY STORAGE HELPERS
    # -------------------------------------------------------------------------
    
    def _store_network_scan(self, scan_id: str, hosts: List[Host]):
        """Store network scan results in Neo4j graph"""
        try:
            # Create scan node
            scan_node = self.agent.mem.upsert_entity(
                scan_id, "network_scan",
                labels=["Scan", "NetworkScan"],
                properties={
                    "timestamp": time.time(),
                    "total_hosts": len(hosts)
                }
            )
            
            # Link to session
            if hasattr(self.agent, 'sess') and self.agent.sess:
                self.agent.mem.link_to_session(self.agent.sess.id, scan_id, "PERFORMED_SCAN")
            
            # Create host nodes
            for host in hosts:
                host_id = f"host_{host.ip.replace('.', '_')}"
                host_node = self.agent.mem.upsert_entity(
                    host_id, "host",
                    labels=["Host", "NetworkHost"],
                    properties={
                        "ip": host.ip,
                        "hostname": host.hostname,
                        "status": host.status,
                        "os": host.os,
                        "mac": host.mac,
                        "vendor": host.vendor,
                        "open_ports": host.open_ports
                    }
                )
                
                # Link to scan
                self.agent.mem.link(scan_id, host_id, "DISCOVERED")
                
        except Exception as e:
            logger.error(f"Failed to store network scan: {e}")
    
    def _store_service_scan(self, scan_id: str, target: str, services: List[Service]):
        """Store service scan results"""
        try:
            scan_node = self.agent.mem.upsert_entity(
                scan_id, "service_scan",
                labels=["Scan", "ServiceScan"],
                properties={
                    "target": target,
                    "timestamp": time.time(),
                    "total_services": len(services)
                }
            )
            
            if hasattr(self.agent, 'sess') and self.agent.sess:
                self.agent.mem.link_to_session(self.agent.sess.id, scan_id, "PERFORMED_SCAN")
            
            for service in services:
                service_id = f"service_{target.replace('.', '_')}_{service.port}"
                service_node = self.agent.mem.upsert_entity(
                    service_id, "service",
                    labels=["Service", "NetworkService"],
                    properties={
                        "port": service.port,
                        "protocol": service.protocol,
                        "service": service.service,
                        "product": service.product,
                        "version": service.version,
                        "banner": service.banner
                    }
                )
                
                self.agent.mem.link(scan_id, service_id, "DETECTED")
                
                # Link CVEs
                if hasattr(service, 'vulnerabilities'):
                    for vuln in service.vulnerabilities:
                        vuln_id = f"cve_{vuln.cve_id}"
                        vuln_node = self.agent.mem.upsert_entity(
                            vuln_id, "vulnerability",
                            labels=["CVE", "Vulnerability"],
                            properties={
                                "cve_id": vuln.cve_id,
                                "description": vuln.description,
                                "cvss_score": vuln.cvss_score,
                                "severity": vuln.severity
                            }
                        )
                        self.agent.mem.link(service_id, vuln_id, "VULNERABLE_TO")
                        
        except Exception as e:
            logger.error(f"Failed to store service scan: {e}")
    
    def _store_dns_scan(self, scan_id: str, domain_info: Domain):
        """Store DNS enumeration results"""
        try:
            domain_id = f"domain_{domain_info.domain.replace('.', '_')}"
            domain_node = self.agent.mem.upsert_entity(
                domain_id, "domain",
                labels=["Domain"],
                properties={
                    "domain": domain_info.domain,
                    "registrar": domain_info.registrar,
                    "creation_date": domain_info.creation_date,
                    "expiration_date": domain_info.expiration_date,
                    "nameservers": domain_info.nameservers,
                    "mx_records": domain_info.mx_records
                }
            )
            
            if hasattr(self.agent, 'sess') and self.agent.sess:
                self.agent.mem.link_to_session(self.agent.sess.id, domain_id, "INVESTIGATED")
            
            # Store subdomains
            for subdomain in domain_info.subdomains:
                sub_id = f"subdomain_{subdomain.replace('.', '_')}"
                sub_node = self.agent.mem.upsert_entity(
                    sub_id, "subdomain",
                    labels=["Subdomain"],
                    properties={"hostname": subdomain}
                )
                self.agent.mem.link(domain_id, sub_id, "HAS_SUBDOMAIN")
                
        except Exception as e:
            logger.error(f"Failed to store DNS scan: {e}")
    
    def _store_webtech_scan(self, scan_id: str, url: str, technologies: List[WebTechnology]):
        """Store web technology detection results"""
        try:
            url_id = f"url_{hashlib.md5(url.encode()).hexdigest()[:16]}"
            url_node = self.agent.mem.upsert_entity(
                url_id, "url",
                labels=["URL", "Website"],
                properties={"url": url}
            )
            
            if hasattr(self.agent, 'sess') and self.agent.sess:
                self.agent.mem.link_to_session(self.agent.sess.id, url_id, "ANALYZED")
            
            for tech in technologies:
                tech_id = f"tech_{tech.name.lower().replace(' ', '_')}"
                tech_node = self.agent.mem.upsert_entity(
                    tech_id, "technology",
                    labels=["Technology", tech.category],
                    properties={
                        "name": tech.name,
                        "version": tech.version,
                        "category": tech.category
                    }
                )
                self.agent.mem.link(url_id, tech_id, "USES", {
                    "confidence": tech.confidence
                })
                
                # Link CVEs
                if hasattr(tech, 'vulnerabilities'):
                    for vuln in tech.vulnerabilities:
                        vuln_id = f"cve_{vuln.cve_id}"
                        vuln_node = self.agent.mem.upsert_entity(
                            vuln_id, "vulnerability",
                            labels=["CVE"],
                            properties={
                                "cve_id": vuln.cve_id,
                                "cvss_score": vuln.cvss_score,
                                "severity": vuln.severity
                            }
                        )
                        self.agent.mem.link(tech_id, vuln_id, "VULNERABLE_TO")
                        
        except Exception as e:
            logger.error(f"Failed to store webtech scan: {e}")
    
    def _store_cve_search(self, scan_id: str, product: str, version: Optional[str], vulns: List[Vulnerability]):
        """Store CVE search results"""
        try:
            product_id = f"product_{product.lower().replace(' ', '_')}"
            if version:
                product_id += f"_{version.replace('.', '_')}"
            
            product_node = self.agent.mem.upsert_entity(
                product_id, "product",
                labels=["Product"],
                properties={
                    "name": product,
                    "version": version
                }
            )
            
            for vuln in vulns:
                vuln_id = f"cve_{vuln.cve_id}"
                vuln_node = self.agent.mem.upsert_entity(
                    vuln_id, "vulnerability",
                    labels=["CVE", "Vulnerability"],
                    properties={
                        "cve_id": vuln.cve_id,
                        "description": vuln.description,
                        "cvss_score": vuln.cvss_score,
                        "severity": vuln.severity,
                        "published": vuln.published
                    }
                )
                self.agent.mem.link(product_id, vuln_id, "AFFECTED_BY")
                
        except Exception as e:
            logger.error(f"Failed to store CVE search: {e}")
    
    def _store_shodan_result(self, scan_id: str, query: str, result: Dict[str, Any]):
        """Store Shodan lookup results"""
        try:
            ip = result.get('ip', query)
            host_id = f"host_{ip.replace('.', '_')}"
            
            self.agent.mem.upsert_entity(
                host_id, "host",
                labels=["Host", "ShodanHost"],
                properties={
                    "ip": ip,
                    "org": result.get('org'),
                    "os": result.get('os'),
                    "hostnames": result.get('hostnames', [])
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to store Shodan result: {e}")
    
    def _store_shodan_results(self, scan_id: str, query: str, results: List[Dict[str, Any]]):
        """Store Shodan search results"""
        for result in results:
            self._store_shodan_result(scan_id, result['ip'], result)
    
    def _store_ssl_scan(self, scan_id: str, hostname: str, result: Dict[str, Any]):
        """Store SSL analysis results"""
        try:
            host_id = f"host_{hostname.replace('.', '_')}"
            cert_data = result.get('certificate', {})
            
            self.agent.mem.upsert_entity(
                host_id, "host",
                labels=["Host", "SSLHost"],
                properties={
                    "hostname": hostname,
                    "ssl_protocol": ','.join(result.get('protocol_versions', [])),
                    "ssl_issues": result.get('issues', []),
                    "cert_subject": cert_data.get('subject', {}),
                    "cert_issuer": cert_data.get('issuer', {}),
                    "cert_valid_until": cert_data.get('notAfter')
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to store SSL scan: {e}")
    
    # -------------------------------------------------------------------------
    # CONVERSION HELPERS
    # -------------------------------------------------------------------------
    
    def _host_to_dict(self, host: Host) -> Dict[str, Any]:
        return {
            "ip": host.ip,
            "hostname": host.hostname,
            "status": host.status,
            "os": host.os,
            "mac": host.mac,
            "vendor": host.vendor,
            "open_ports": host.open_ports
        }
    
    def _service_to_dict(self, service: Service) -> Dict[str, Any]:
        result = {
            "port": service.port,
            "protocol": service.protocol,
            "service": service.service,
            "version": service.version,
            "product": service.product,
            "banner": service.banner
        }
        if hasattr(service, 'vulnerabilities'):
            result["vulnerabilities"] = [self._vuln_to_dict(v) for v in service.vulnerabilities]
        return result
    
    def _vuln_to_dict(self, vuln: Vulnerability) -> Dict[str, Any]:
        return {
            "cve_id": vuln.cve_id,
            "description": vuln.description,
            "cvss_score": vuln.cvss_score,
            "severity": vuln.severity,
            "published": vuln.published
        }
    
    def _tech_to_dict(self, tech: WebTechnology) -> Dict[str, Any]:
        result = {
            "name": tech.name,
            "version": tech.version,
            "category": tech.category,
            "confidence": tech.confidence
        }
        if hasattr(tech, 'vulnerabilities'):
            result["vulnerabilities"] = [self._vuln_to_dict(v) for v in tech.vulnerabilities]
        return result
    
    def _domain_to_dict(self, domain: Domain) -> Dict[str, Any]:
        return {
            "domain": domain.domain,
            "subdomains": domain.subdomains,
            "nameservers": domain.nameservers,
            "mx_records": domain.mx_records,
            "registrar": domain.registrar,
            "creation_date": domain.creation_date,
            "expiration_date": domain.expiration_date
        }


# =============================================================================
# TOOL LOADER INTEGRATION
# =============================================================================

def add_all_network_osint_tools(tool_list: List, agent):
    """
    Add all OSINT tools to the tool list.
    
    Usage in tools.py:
        from Vera.Toolchain.Tools.OSINT.loader import add_all_osint_tools
        
        def ToolLoader(agent):
            tool_list = [...]
            add_all_osint_tools(tool_list, agent)
            return tool_list
    """
    
    osint = OSINTTools(agent)
    
    # Network scanning tools
    if NMAP_AVAILABLE:
        tool_list.append(
            StructuredTool.from_function(
                func=osint.scan_network,
                name="scan_network",
                description=(
                    "Scan network for hosts, ports, and services. "
                    "Supports CIDR ranges, individual IPs, and hostnames. "
                    "Three scan types: 'quick' (fast host discovery), 'normal' (standard port scan), "
                    "'intensive' (OS detection + scripts). Results stored in graph memory."
                ),
                args_schema=NetworkScanInput
            )
        )
        
        tool_list.append(
            StructuredTool.from_function(
                func=osint.scan_services,
                name="scan_services",
                description=(
                    "Detailed service detection and fingerprinting on a target. "
                    "Identifies service versions, products, banners, and automatically "
                    "maps services to known CVE vulnerabilities. Essential for vulnerability assessment."
                ),
                args_schema=ServiceScanInput
            )
        )
    
    # DNS reconnaissance tools
    if DNS_AVAILABLE:
        tool_list.append(
            StructuredTool.from_function(
                func=osint.enumerate_dns,
                name="enumerate_dns",
                description=(
                    "Comprehensive DNS reconnaissance for a domain. "
                    "Gathers A, NS, MX, TXT records, WHOIS data, and performs subdomain enumeration. "
                    "Optionally attempts zone transfer (AXFR). Results organized in graph with domain as central node."
                ),
                args_schema=DNSEnumInput
            )
        )
    
    # Web reconnaissance tools
    tool_list.append(
        StructuredTool.from_function(
            func=osint.detect_web_technologies,
            name="detect_web_technologies",
            description=(
                "Identify technologies and frameworks used by a website. "
                "Detects CMS systems, JavaScript frameworks, web servers, analytics, CDNs. "
                "Automatically maps detected technologies to known CVEs for vulnerability assessment."
            ),
            args_schema=WebTechInput
        )
    )
    
    # Vulnerability mapping tools
    tool_list.append(
        StructuredTool.from_function(
            func=osint.search_cves,
            name="search_cves",
            description=(
                "Search National Vulnerability Database for CVEs affecting a product. "
                "Returns CVE IDs, CVSS scores, severity ratings, and detailed descriptions. "
                "Essential for vulnerability assessment and patch management."
            ),
            args_schema=CVESearchInput
        )
    )
    
    # Shodan tools (if available)
    if osint.shodan_client:
        tool_list.append(
            StructuredTool.from_function(
                func=osint.shodan_search,
                name="shodan_search",
                description=(
                    "Search Shodan database for exposed services and hosts. "
                    "Passive reconnaissance - query historical scan data without direct scanning. "
                    "Two modes: 'ip' for specific host lookup, 'query' for custom Shodan searches. "
                    "Reveals open ports, services, vulnerabilities, and organization info."
                ),
                args_schema=ShodanSearchInput
            )
        )
    
    # SSL/TLS analysis tools
    tool_list.append(
        StructuredTool.from_function(
            func=osint.analyze_ssl,
            name="analyze_ssl",
            description=(
                "Analyze SSL/TLS certificate and security configuration. "
                "Checks certificate validity, expiration, issuer, protocol versions, "
                "cipher suites, and identifies common SSL/TLS vulnerabilities. "
                "Essential for web security assessment."
            ),
            args_schema=SSLAnalysisInput
        )
    )
    
    # Export tools
    tool_list.append(
        StructuredTool.from_function(
            func=osint.export_scan_results,
            name="export_scan_results",
            description=(
                "Export OSINT scan results to file. "
                "Formats: 'json' (structured data) or 'markdown' (human-readable report). "
                "Use scan ID from previous scan output."
            ),
            args_schema=ExportResultsInput
        )
    )
    
    logger.info(f"Added {len([t for t in tool_list if 'scan' in t.name or 'search' in t.name or 'detect' in t.name or 'analyze' in t.name])} OSINT tools")
    
    return tool_list


# =============================================================================
# STANDALONE TESTING
# =============================================================================

if __name__ == "__main__":
    print("OSINT Tools Loader - Testing")
    print("\nThis module should be imported by tools.py")
    print("\nUsage:")
    print("  from Vera.Toolchain.Tools.OSINT.loader import add_all_osint_tools")
    print("  add_all_osint_tools(tool_list, agent)")