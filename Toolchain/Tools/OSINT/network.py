#!/usr/bin/env python3
"""
Comprehensive OSINT Toolkit for Network Reconnaissance and Vulnerability Assessment

Features:
- Network scanning (host discovery, port scanning, service detection)
- Domain/subdomain enumeration
- Technology stack detection
- CVE/vulnerability mapping
- SSL/TLS analysis
- DNS reconnaissance
- WHOIS lookups
- Shodan/Censys integration
- Results stored in Neo4j graph + ChromaDB vectors

Dependencies:
    pip install nmap python-nmap dnspython shodan censys requests beautifulsoup4
    pip install python-whois ssl-analyzer builtwith
    sudo apt-get install nmap  # For system-level nmap
"""

import json
import time
import socket
import ssl
import hashlib
import requests
import subprocess
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urlparse
import logging

# Network scanning
try:
    import nmap
    NMAP_AVAILABLE = True
except ImportError:
    NMAP_AVAILABLE = False
    print("[Warning] python-nmap not available. Install: pip install python-nmap")

# DNS
try:
    import dns.resolver
    import dns.zone
    import dns.query
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False
    print("[Warning] dnspython not available. Install: pip install dnspython")

# WHOIS
try:
    import whois
    WHOIS_AVAILABLE = True
except ImportError:
    WHOIS_AVAILABLE = False
    print("[Warning] python-whois not available. Install: pip install python-whois")

# Shodan
try:
    import shodan
    SHODAN_AVAILABLE = True
except ImportError:
    SHODAN_AVAILABLE = False
    print("[Warning] Shodan not available. Install: pip install shodan")

# Web tech detection
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class Host:
    """Discovered network host"""
    ip: str
    hostname: Optional[str] = None
    status: str = "unknown"
    os: Optional[str] = None
    mac: Optional[str] = None
    vendor: Optional[str] = None
    open_ports: List[int] = None
    
    def __post_init__(self):
        if self.open_ports is None:
            self.open_ports = []

@dataclass
class Service:
    """Network service on a port"""
    port: int
    protocol: str
    service: str
    version: Optional[str] = None
    product: Optional[str] = None
    cpe: Optional[str] = None
    banner: Optional[str] = None
    state: str = "open"

@dataclass
class Vulnerability:
    """CVE vulnerability"""
    cve_id: str
    description: str
    cvss_score: Optional[float] = None
    severity: Optional[str] = None
    published: Optional[str] = None
    references: List[str] = None
    affected_products: List[str] = None
    
    def __post_init__(self):
        if self.references is None:
            self.references = []
        if self.affected_products is None:
            self.affected_products = []

@dataclass
class WebTechnology:
    """Detected web technology"""
    name: str
    version: Optional[str] = None
    category: str = "unknown"
    confidence: float = 1.0
    evidence: List[str] = None
    
    def __post_init__(self):
        if self.evidence is None:
            self.evidence = []

@dataclass
class Domain:
    """Domain information"""
    domain: str
    subdomains: List[str] = None
    nameservers: List[str] = None
    mx_records: List[str] = None
    txt_records: List[str] = None
    registrar: Optional[str] = None
    creation_date: Optional[str] = None
    expiration_date: Optional[str] = None
    
    def __post_init__(self):
        if self.subdomains is None:
            self.subdomains = []
        if self.nameservers is None:
            self.nameservers = []
        if self.mx_records is None:
            self.mx_records = []
        if self.txt_records is None:
            self.txt_records = []


# =============================================================================
# NETWORK SCANNER
# =============================================================================

class NetworkScanner:
    """Active network reconnaissance using nmap"""
    
    def __init__(self):
        if not NMAP_AVAILABLE:
            raise ImportError("python-nmap required. Install: pip install python-nmap")
        self.nm = nmap.PortScanner()
    
    def scan_network(self, target: str, ports: str = "1-1000", 
                    arguments: str = "-sV -O -A") -> List[Host]:
        """
        Comprehensive network scan.
        
        Args:
            target: IP, CIDR, or hostname (e.g., "192.168.1.0/24")
            ports: Port range (e.g., "1-1000", "80,443,8080")
            arguments: Nmap arguments (default: service + OS detection)
        
        Returns:
            List of discovered hosts with services
        """
        logger.info(f"Scanning network: {target} ports {ports}")
        
        try:
            self.nm.scan(hosts=target, ports=ports, arguments=arguments)
        except Exception as e:
            logger.error(f"Scan failed: {e}")
            return []
        
        hosts = []
        for host_ip in self.nm.all_hosts():
            host = Host(ip=host_ip)
            
            if 'hostnames' in self.nm[host_ip]:
                hostnames = self.nm[host_ip]['hostnames']
                if hostnames and len(hostnames) > 0:
                    host.hostname = hostnames[0].get('name', '')
            
            host.status = self.nm[host_ip].state()
            
            # OS detection
            if 'osmatch' in self.nm[host_ip]:
                if self.nm[host_ip]['osmatch']:
                    host.os = self.nm[host_ip]['osmatch'][0].get('name', '')
            
            # MAC address
            if 'mac' in self.nm[host_ip]['addresses']:
                host.mac = self.nm[host_ip]['addresses']['mac']
            
            if 'vendor' in self.nm[host_ip]:
                if host.mac and host.mac in self.nm[host_ip]['vendor']:
                    host.vendor = self.nm[host_ip]['vendor'][host.mac]
            
            # Open ports
            for proto in self.nm[host_ip].all_protocols():
                ports = self.nm[host_ip][proto].keys()
                host.open_ports.extend(list(ports))
            
            hosts.append(host)
        
        logger.info(f"Discovered {len(hosts)} hosts")
        return hosts
    
    def scan_services(self, target: str, ports: str = "1-1000") -> List[Service]:
        """
        Detailed service detection on open ports.
        
        Args:
            target: IP or hostname
            ports: Port range to scan
        
        Returns:
            List of detected services
        """
        logger.info(f"Scanning services: {target} ports {ports}")
        
        try:
            self.nm.scan(hosts=target, ports=ports, arguments="-sV --version-all")
        except Exception as e:
            logger.error(f"Service scan failed: {e}")
            return []
        
        services = []
        if target not in self.nm.all_hosts():
            return services
        
        for proto in self.nm[target].all_protocols():
            ports_info = self.nm[target][proto]
            
            for port, info in ports_info.items():
                service = Service(
                    port=port,
                    protocol=proto,
                    service=info.get('name', 'unknown'),
                    version=info.get('version', ''),
                    product=info.get('product', ''),
                    cpe=info.get('cpe', ''),
                    state=info.get('state', 'unknown')
                )
                
                # Try to get banner
                try:
                    banner = self._grab_banner(target, port)
                    if banner:
                        service.banner = banner
                except:
                    pass
                
                services.append(service)
        
        logger.info(f"Detected {len(services)} services")
        return services
    
    def _grab_banner(self, host: str, port: int, timeout: int = 3) -> Optional[str]:
        """Grab service banner"""
        try:
            sock = socket.socket()
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.send(b'\r\n')
            banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()
            sock.close()
            return banner
        except:
            return None
    
    def quick_scan(self, target: str) -> Dict[str, Any]:
        """
        Quick ping scan for host discovery.
        
        Args:
            target: Network range (e.g., "192.168.1.0/24")
        
        Returns:
            Dict with live hosts and basic info
        """
        logger.info(f"Quick scan: {target}")
        
        try:
            self.nm.scan(hosts=target, arguments="-sn")  # Ping scan
        except Exception as e:
            logger.error(f"Quick scan failed: {e}")
            return {"hosts": [], "total": 0}
        
        live_hosts = []
        for host in self.nm.all_hosts():
            info = {
                "ip": host,
                "hostname": "",
                "status": self.nm[host].state()
            }
            
            if 'hostnames' in self.nm[host]:
                hostnames = self.nm[host]['hostnames']
                if hostnames and len(hostnames) > 0:
                    info["hostname"] = hostnames[0].get('name', '')
            
            live_hosts.append(info)
        
        return {
            "hosts": live_hosts,
            "total": len(live_hosts),
            "scan_time": datetime.now().isoformat()
        }


# =============================================================================
# DNS RECONNAISSANCE
# =============================================================================

class DNSRecon:
    """DNS enumeration and reconnaissance"""
    
    def __init__(self):
        if not DNS_AVAILABLE:
            raise ImportError("dnspython required. Install: pip install dnspython")
        self.resolver = dns.resolver.Resolver()
    
    def enumerate_dns(self, domain: str) -> Domain:
        """
        Comprehensive DNS enumeration.
        
        Args:
            domain: Target domain
        
        Returns:
            Domain object with DNS records
        """
        logger.info(f"DNS enumeration: {domain}")
        
        domain_obj = Domain(domain=domain)
        
        # A records (IPv4)
        try:
            answers = self.resolver.resolve(domain, 'A')
            domain_obj.a_records = [str(rdata) for rdata in answers]
        except:
            domain_obj.a_records = []
        
        # NS records (nameservers)
        try:
            answers = self.resolver.resolve(domain, 'NS')
            domain_obj.nameservers = [str(rdata) for rdata in answers]
        except:
            pass
        
        # MX records (mail servers)
        try:
            answers = self.resolver.resolve(domain, 'MX')
            domain_obj.mx_records = [f"{rdata.preference} {rdata.exchange}" for rdata in answers]
        except:
            pass
        
        # TXT records
        try:
            answers = self.resolver.resolve(domain, 'TXT')
            domain_obj.txt_records = [str(rdata) for rdata in answers]
        except:
            pass
        
        # WHOIS if available
        if WHOIS_AVAILABLE:
            try:
                w = whois.whois(domain)
                domain_obj.registrar = w.registrar
                if w.creation_date:
                    if isinstance(w.creation_date, list):
                        domain_obj.creation_date = str(w.creation_date[0])
                    else:
                        domain_obj.creation_date = str(w.creation_date)
                if w.expiration_date:
                    if isinstance(w.expiration_date, list):
                        domain_obj.expiration_date = str(w.expiration_date[0])
                    else:
                        domain_obj.expiration_date = str(w.expiration_date)
            except:
                pass
        
        return domain_obj
    
    def enumerate_subdomains(self, domain: str, wordlist: Optional[List[str]] = None) -> List[str]:
        """
        Subdomain enumeration via brute force and DNS queries.
        
        Args:
            domain: Target domain
            wordlist: List of subdomain prefixes to try
        
        Returns:
            List of discovered subdomains
        """
        if wordlist is None:
            # Common subdomain prefixes
            wordlist = [
                'www', 'mail', 'ftp', 'localhost', 'webmail', 'smtp', 'pop', 'ns1', 'webdisk',
                'ns2', 'cpanel', 'whm', 'autodiscover', 'autoconfig', 'm', 'imap', 'test',
                'ns', 'blog', 'pop3', 'dev', 'www2', 'admin', 'forum', 'news', 'vpn', 'ns3',
                'mail2', 'new', 'mysql', 'old', 'lists', 'support', 'mobile', 'mx', 'static',
                'docs', 'beta', 'shop', 'sql', 'secure', 'demo', 'cp', 'calendar', 'wiki',
                'web', 'media', 'email', 'images', 'img', 'www1', 'intranet', 'portal',
                'video', 'sip', 'dns2', 'api', 'cdn', 'stats', 'dns1', 'ns4', 'www3', 'dns',
                'search', 'staging', 'server', 'mx1', 'chat', 'wap', 'my', 'svn', 'mail1',
                'sites', 'proxy', 'ads', 'host', 'crm', 'cms', 'backup', 'mx2', 'lyncdiscover',
                'info', 'apps', 'download', 'remote', 'db', 'forums', 'store', 'relay',
                'files', 'newsletter', 'app', 'live', 'owa', 'en', 'start', 'sms', 'office',
                'exchange', 'ipv4', 'prod', 'help', 'git', 'upload', 'cloud', 'stage'
            ]
        
        logger.info(f"Enumerating subdomains for {domain} using {len(wordlist)} prefixes")
        
        discovered = []
        for prefix in wordlist:
            subdomain = f"{prefix}.{domain}"
            try:
                answers = self.resolver.resolve(subdomain, 'A')
                if answers:
                    discovered.append(subdomain)
                    logger.debug(f"Found subdomain: {subdomain}")
            except:
                pass
        
        logger.info(f"Discovered {len(discovered)} subdomains")
        return discovered
    
    def dns_zone_transfer(self, domain: str) -> List[str]:
        """
        Attempt DNS zone transfer (AXFR).
        
        Note: This usually fails on properly configured DNS servers.
        
        Args:
            domain: Target domain
        
        Returns:
            List of records if successful, empty if failed
        """
        logger.info(f"Attempting zone transfer for {domain}")
        
        records = []
        
        try:
            # Get nameservers
            ns_answers = self.resolver.resolve(domain, 'NS')
            nameservers = [str(rdata) for rdata in ns_answers]
            
            for ns in nameservers:
                try:
                    # Attempt AXFR
                    zone = dns.zone.from_xfr(dns.query.xfr(ns, domain))
                    for name, node in zone.nodes.items():
                        records.append(f"{name}.{domain}")
                    
                    logger.info(f"Zone transfer successful from {ns}")
                    break
                except:
                    continue
        except:
            pass
        
        return records
    
    def reverse_dns(self, ip: str) -> Optional[str]:
        """
        Reverse DNS lookup.
        
        Args:
            ip: IP address
        
        Returns:
            Hostname if found
        """
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return hostname
        except:
            return None


# =============================================================================
# WEB TECHNOLOGY DETECTION
# =============================================================================

class WebTechDetector:
    """Enhanced web technology fingerprinting with JSON configuration"""
    
    def __init__(self, signatures_file: Optional[str] = None):
        self.signatures = self._load_signatures(signatures_file)
        self.confidence_threshold = 0.3  # Minimum confidence to report
    
    def _load_signatures(self, file_path: Optional[str]) -> Dict[str, Any]:
        """Load technology signatures from JSON file (Wappalyzer-style)"""
        
        # Default to tech_signatures.json in same directory
        if file_path is None:
            file_path = Path(__file__).parent / "tech_signatures.json"
        
        signatures = {}
        
        # Try to load from file
        if file_path and Path(file_path).exists():
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    signatures = data.get('technologies', {})
                    logger.info(f"Loaded {len(signatures)} technology signatures from {file_path}")
            except Exception as e:
                logger.error(f"Failed to load signatures from {file_path}: {e}")
        
        # Fallback to minimal built-in signatures if file loading failed
        if not signatures:
            logger.warning("Using minimal built-in signatures (tech_signatures.json not found)")
            signatures = {
                "WordPress": {
                    "category": "CMS",
                    "patterns": {
                        "html": [r'<meta name="generator" content="WordPress'],
                        "scripts": ["/wp-content/", "/wp-includes/"]
                    }
                },
                "React": {
                    "category": "JavaScript Framework",
                    "patterns": {
                        "html": [r'data-react'],
                        "scripts": ["react.min.js", "react-dom"]
                    }
                },
                "nginx": {
                    "category": "Web Server",
                    "patterns": {
                        "headers": {"Server": "nginx"}
                    }
                }
            }
        
        return signatures
    
    def detect(self, url: str) -> List[WebTechnology]:
        """
        Detect technologies used by a website using JSON signatures.
        
        Args:
            url: Target URL
        
        Returns:
            List of detected technologies with confidence scores
        """
        logger.info(f"Detecting technologies for {url}")
        
        technologies = []
        
        try:
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            html = response.text
            headers = response.headers
            cookies = response.cookies
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract scripts and CSS
            scripts = [tag.get('src', '') for tag in soup.find_all('script') if tag.get('src')]
            css_links = [tag.get('href', '') for tag in soup.find_all('link', rel='stylesheet') if tag.get('href')]
            
            # Extract meta tags
            meta_tags = {}
            for meta in soup.find_all('meta'):
                name = meta.get('name', meta.get('property', ''))
                content = meta.get('content', '')
                if name and content:
                    meta_tags[name.lower()] = content
            
            # Check each signature
            for tech_name, sig in self.signatures.items():
                evidence = []
                confidence = 0.0
                patterns = sig.get('patterns', {})
                
                # Confidence weight from signature (default 1.0)
                base_weight = sig.get('confidence_weight', 1.0)
                
                # Check HTML patterns
                if 'html' in patterns:
                    for pattern in patterns['html']:
                        if re.search(pattern, html, re.IGNORECASE):
                            evidence.append(f"HTML pattern: {pattern[:50]}")
                            confidence += 0.3 * base_weight
                
                # Check headers
                if 'headers' in patterns:
                    for header, value_pattern in patterns['headers'].items():
                        if header in headers:
                            header_value = headers[header]
                            if not value_pattern or re.search(value_pattern, header_value, re.IGNORECASE):
                                evidence.append(f"Header: {header}={header_value}")
                                confidence += 0.4 * base_weight
                
                # Check cookies
                if 'cookies' in patterns:
                    for cookie_pattern, _ in patterns['cookies'].items():
                        for cookie in cookies:
                            if re.search(cookie_pattern, cookie, re.IGNORECASE):
                                evidence.append(f"Cookie: {cookie}")
                                confidence += 0.3 * base_weight
                
                # Check scripts
                if 'scripts' in patterns:
                    for pattern in patterns['scripts']:
                        for script in scripts:
                            if re.search(pattern, script, re.IGNORECASE):
                                evidence.append(f"Script: {script[:80]}")
                                confidence += 0.25 * base_weight
                
                # Check CSS
                if 'css' in patterns:
                    for pattern in patterns['css']:
                        for css in css_links:
                            if re.search(pattern, css, re.IGNORECASE):
                                evidence.append(f"CSS: {css[:80]}")
                                confidence += 0.2 * base_weight
                
                # Check meta tags
                if 'meta' in patterns:
                    for meta_name, meta_pattern in patterns['meta'].items():
                        if meta_name in meta_tags:
                            if re.search(meta_pattern, meta_tags[meta_name], re.IGNORECASE):
                                evidence.append(f"Meta: {meta_name}={meta_tags[meta_name][:50]}")
                                confidence += 0.35 * base_weight
                
                # Check DOM elements (if specified)
                if 'dom' in patterns:
                    for selector, _ in patterns['dom'].items():
                        try:
                            if soup.select(selector):
                                evidence.append(f"DOM: {selector}")
                                confidence += 0.3 * base_weight
                        except:
                            pass
                
                # Add technology if confidence exceeds threshold
                if evidence and confidence >= self.confidence_threshold:
                    tech = WebTechnology(
                        name=tech_name,
                        category=sig.get('category', 'unknown'),
                        confidence=min(confidence, 1.0),
                        evidence=evidence[:5]  # Limit evidence
                    )
                    
                    # Try to extract version
                    version = self._extract_version_from_pattern(
                        html, 
                        headers, 
                        scripts, 
                        sig.get('version_pattern', '')
                    )
                    if version:
                        tech.version = version
                    
                    technologies.append(tech)
            
            # Sort by confidence
            technologies.sort(key=lambda t: t.confidence, reverse=True)
            
            logger.info(f"Detected {len(technologies)} technologies")
            
        except Exception as e:
            logger.error(f"Technology detection failed: {e}")
        
        return technologies
    
    def _extract_version_from_pattern(self, html: str, headers: Dict, scripts: List[str], version_pattern: str) -> Optional[str]:
        """Extract version using pattern from signature"""
        
        if not version_pattern:
            return None
        
        # Try HTML
        match = re.search(version_pattern, html, re.IGNORECASE)
        if match and match.groups():
            return match.group(1)
        
        # Try headers
        for header, value in headers.items():
            match = re.search(version_pattern, value, re.IGNORECASE)
            if match and match.groups():
                return match.group(1)
        
        # Try scripts
        for script in scripts:
            match = re.search(version_pattern, script, re.IGNORECASE)
            if match and match.groups():
                return match.group(1)
        
        return None


# =============================================================================
# CVE/VULNERABILITY MAPPER
# =============================================================================

class CVEMapper:
    """Map services and technologies to known CVEs"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.nvd_base = "https://services.nvd.nist.gov/rest/json/cves/2.0"
        self.cache = {}  # Simple cache to avoid repeated API calls
    
    def search_cves(self, product: str, version: Optional[str] = None, 
                   max_results: int = 10) -> List[Vulnerability]:
        """
        Search NVD database for CVEs affecting a product.
        
        Args:
            product: Product name (e.g., "apache", "wordpress")
            version: Specific version (optional)
            max_results: Maximum CVEs to return
        
        Returns:
            List of vulnerabilities
        """
        logger.info(f"Searching CVEs for {product} {version or ''}")
        
        cache_key = f"{product}:{version or 'any'}"
        if cache_key in self.cache:
            logger.debug("Returning cached CVE results")
            return self.cache[cache_key][:max_results]
        
        vulnerabilities = []
        
        try:
            # Build query
            params = {
                "keywordSearch": product,
                "resultsPerPage": max_results
            }
            
            if version:
                params["keywordSearch"] = f"{product} {version}"
            
            headers = {}
            if self.api_key:
                headers["apiKey"] = self.api_key
            
            response = requests.get(self.nvd_base, params=params, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'vulnerabilities' in data:
                    for item in data['vulnerabilities']:
                        cve_data = item.get('cve', {})
                        
                        cve_id = cve_data.get('id', '')
                        
                        # Description
                        descriptions = cve_data.get('descriptions', [])
                        description = ""
                        if descriptions:
                            description = descriptions[0].get('value', '')
                        
                        # CVSS score
                        metrics = cve_data.get('metrics', {})
                        cvss_score = None
                        severity = None
                        
                        if 'cvssMetricV31' in metrics and metrics['cvssMetricV31']:
                            cvss_data = metrics['cvssMetricV31'][0]
                            cvss_score = cvss_data.get('cvssData', {}).get('baseScore')
                            severity = cvss_data.get('cvssData', {}).get('baseSeverity')
                        elif 'cvssMetricV2' in metrics and metrics['cvssMetricV2']:
                            cvss_data = metrics['cvssMetricV2'][0]
                            cvss_score = cvss_data.get('cvssData', {}).get('baseScore')
                        
                        # Published date
                        published = cve_data.get('published', '')
                        
                        # References
                        refs = []
                        if 'references' in cve_data:
                            refs = [ref.get('url', '') for ref in cve_data['references'][:5]]
                        
                        vuln = Vulnerability(
                            cve_id=cve_id,
                            description=description[:500],  # Truncate
                            cvss_score=cvss_score,
                            severity=severity,
                            published=published,
                            references=refs,
                            affected_products=[product]
                        )
                        
                        vulnerabilities.append(vuln)
            
            # Cache results
            self.cache[cache_key] = vulnerabilities
            logger.info(f"Found {len(vulnerabilities)} CVEs")
            
        except Exception as e:
            logger.error(f"CVE search failed: {e}")
        
        return vulnerabilities[:max_results]
    
    def map_service_to_cves(self, service: Service) -> List[Vulnerability]:
        """Map a service to its vulnerabilities"""
        
        product = service.product or service.service
        version = service.version
        
        if not product or product == "unknown":
            return []
        
        return self.search_cves(product, version, max_results=5)
    
    def map_technology_to_cves(self, tech: WebTechnology) -> List[Vulnerability]:
        """Map a web technology to its vulnerabilities"""
        
        return self.search_cves(tech.name, tech.version, max_results=5)


# =============================================================================
# SHODAN INTEGRATION
# =============================================================================

class ShodanClient:
    """Shodan search engine integration for passive reconnaissance"""
    
    def __init__(self, api_key: str):
        if not SHODAN_AVAILABLE:
            raise ImportError("shodan required. Install: pip install shodan")
        
        self.api = shodan.Shodan(api_key)
    
    def search_host(self, ip: str) -> Dict[str, Any]:
        """
        Lookup host in Shodan database.
        
        Args:
            ip: IP address
        
        Returns:
            Dict with host information
        """
        try:
            host_info = self.api.host(ip)
            return {
                "ip": host_info.get('ip_str'),
                "org": host_info.get('org'),
                "os": host_info.get('os'),
                "ports": host_info.get('ports', []),
                "hostnames": host_info.get('hostnames', []),
                "vulns": host_info.get('vulns', []),
                "tags": host_info.get('tags', []),
                "services": [
                    {
                        "port": item.get('port'),
                        "protocol": item.get('transport'),
                        "product": item.get('product'),
                        "version": item.get('version'),
                        "banner": item.get('data', '')[:200]
                    }
                    for item in host_info.get('data', [])
                ]
            }
        except Exception as e:
            logger.error(f"Shodan lookup failed: {e}")
            return {}
    
    def search_query(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search Shodan using custom query.
        
        Args:
            query: Shodan search query (e.g., "apache port:80")
            max_results: Maximum results
        
        Returns:
            List of matching hosts
        """
        try:
            results = self.api.search(query, page=1)
            
            hosts = []
            for result in results['matches'][:max_results]:
                hosts.append({
                    "ip": result.get('ip_str'),
                    "port": result.get('port'),
                    "org": result.get('org'),
                    "hostnames": result.get('hostnames', []),
                    "product": result.get('product'),
                    "version": result.get('version'),
                    "banner": result.get('data', '')[:200]
                })
            
            return hosts
        except Exception as e:
            logger.error(f"Shodan search failed: {e}")
            return []


# =============================================================================
# SSL/TLS ANALYZER
# =============================================================================

class SSLAnalyzer:
    """SSL/TLS certificate and configuration analysis"""
    
    def analyze_ssl(self, hostname: str, port: int = 443) -> Dict[str, Any]:
        """
        Analyze SSL/TLS certificate and configuration.
        
        Args:
            hostname: Target hostname
            port: SSL port (default 443)
        
        Returns:
            Dict with certificate info and security assessment
        """
        logger.info(f"Analyzing SSL for {hostname}:{port}")
        
        result = {
            "hostname": hostname,
            "port": port,
            "certificate": {},
            "protocol_versions": [],
            "ciphers": [],
            "issues": []
        }
        
        try:
            context = ssl.create_default_context()
            
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
                    
                    # Certificate info
                    result["certificate"] = {
                        "subject": dict(x[0] for x in cert.get('subject', [])),
                        "issuer": dict(x[0] for x in cert.get('issuer', [])),
                        "version": cert.get('version'),
                        "serialNumber": cert.get('serialNumber'),
                        "notBefore": cert.get('notBefore'),
                        "notAfter": cert.get('notAfter'),
                        "subjectAltName": cert.get('subjectAltName', [])
                    }
                    
                    # Protocol version
                    result["protocol_versions"] = [version]
                    
                    # Cipher
                    if cipher:
                        result["ciphers"] = [{
                            "name": cipher[0],
                            "protocol": cipher[1],
                            "bits": cipher[2]
                        }]
                    
                    # Check for issues
                    self._check_ssl_issues(result)
        
        except Exception as e:
            logger.error(f"SSL analysis failed: {e}")
            result["error"] = str(e)
        
        return result
    
    def _check_ssl_issues(self, result: Dict[str, Any]):
        """Check for common SSL/TLS security issues"""
        
        issues = []
        
        # Check certificate expiration
        if 'notAfter' in result['certificate']:
            try:
                expiry = datetime.strptime(result['certificate']['notAfter'], '%b %d %H:%M:%S %Y %Z')
                days_until_expiry = (expiry - datetime.now()).days
                
                if days_until_expiry < 0:
                    issues.append("Certificate has expired")
                elif days_until_expiry < 30:
                    issues.append(f"Certificate expires soon ({days_until_expiry} days)")
            except:
                pass
        
        # Check for weak protocols
        weak_protocols = ['SSLv2', 'SSLv3', 'TLSv1', 'TLSv1.1']
        for version in result.get('protocol_versions', []):
            if version in weak_protocols:
                issues.append(f"Weak protocol: {version}")
        
        # Check for weak ciphers
        weak_ciphers = ['DES', 'RC4', 'MD5', 'NULL', 'EXPORT']
        for cipher in result.get('ciphers', []):
            cipher_name = cipher.get('name', '').upper()
            for weak in weak_ciphers:
                if weak in cipher_name:
                    issues.append(f"Weak cipher: {cipher_name}")
                    break
        
        result["issues"] = issues


# =============================================================================
# EXPORT FUNCTIONS
# =============================================================================

def export_to_json(data: Any, output_file: str):
    """Export scan results to JSON"""
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    logger.info(f"Results exported to {output_file}")


def export_to_markdown(data: Dict[str, Any], output_file: str):
    """Export scan results to Markdown report"""
    
    md_lines = [
        f"# OSINT Reconnaissance Report",
        f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"\n---\n"
    ]
    
    # Hosts
    if 'hosts' in data:
        md_lines.append("\n## 🖥️ Discovered Hosts\n")
        for host in data['hosts']:
            md_lines.append(f"\n### {host.get('ip')} ({host.get('hostname', 'Unknown')})\n")
            md_lines.append(f"- **Status:** {host.get('status')}")
            md_lines.append(f"- **OS:** {host.get('os', 'Unknown')}")
            md_lines.append(f"- **Open Ports:** {', '.join(map(str, host.get('open_ports', [])))}")
    
    # Services
    if 'services' in data:
        md_lines.append("\n## 🔌 Detected Services\n")
        for service in data['services']:
            md_lines.append(f"- **Port {service.get('port')}/{service.get('protocol')}:** "
                          f"{service.get('service')} {service.get('version', '')}")
    
    # Technologies
    if 'technologies' in data:
        md_lines.append("\n## 🛠️ Web Technologies\n")
        for tech in data['technologies']:
            md_lines.append(f"- **{tech.get('name')}** ({tech.get('category')}) "
                          f"- Confidence: {tech.get('confidence', 0):.0%}")
    
    # Vulnerabilities
    if 'vulnerabilities' in data:
        md_lines.append("\n## 🔴 Vulnerabilities\n")
        for vuln in data['vulnerabilities']:
            md_lines.append(f"\n### {vuln.get('cve_id')} - {vuln.get('severity', 'Unknown')}")
            md_lines.append(f"\n**CVSS Score:** {vuln.get('cvss_score', 'N/A')}")
            md_lines.append(f"\n{vuln.get('description', '')}\n")
    
    with open(output_file, 'w') as f:
        f.write('\n'.join(md_lines))
    
    logger.info(f"Report exported to {output_file}")


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    # Example usage
    print("=== OSINT Toolkit Test ===\n")
    
    # Network scanning
    if NMAP_AVAILABLE:
        scanner = NetworkScanner()
        print("Quick scan of local network...")
        # result = scanner.quick_scan("192.168.1.0/24")
        # print(f"Found {result['total']} hosts")
    
    # DNS recon
    if DNS_AVAILABLE:
        dns_recon = DNSRecon()
        print("\nDNS enumeration for example.com...")
        domain_info = dns_recon.enumerate_dns("example.com")
        print(f"Nameservers: {domain_info.nameservers}")
    
    # Web tech detection
    detector = WebTechDetector()
    print("\nDetecting technologies for https://example.com...")
    techs = detector.detect("https://example.com")
    for tech in techs[:5]:
        print(f"- {tech.name} ({tech.category})")
    
    # CVE mapping
    cve_mapper = CVEMapper()
    print("\nSearching CVEs for Apache...")
    vulns = cve_mapper.search_cves("apache", max_results=3)
    for vuln in vulns:
        print(f"- {vuln.cve_id}: {vuln.description[:100]}...")
    
    print("\n=== Tests Complete ===")