#!/usr/bin/env python3
"""
Comprehensive Network Scanner for Vera - INTEGRATED OSINT TOOLKIT
Modular, tool-chaining compatible, with advanced reconnaissance capabilities

FEATURES:
- Host discovery (ping, TCP, nmap)
- Port scanning (socket-based, nmap-enhanced)
- Service detection with banner grabbing
- DNS reconnaissance and enumeration
- SSL/TLS certificate analysis
- Web technology fingerprinting
- Shodan integration for passive recon
- Full graph memory integration
- Tool chaining compatible
- Intelligent input parsing

DEPENDENCIES:
    pip install requests beautifulsoup4
    pip install python-nmap dnspython python-whois shodan  # Optional advanced features
    sudo apt-get install nmap  # For nmap features
"""

import socket
import subprocess
import requests
import json
import re
import time
import ssl
import ipaddress
from typing import List, Dict, Any, Optional, Set, Iterator, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydantic import BaseModel, Field
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse
import logging

# Optional imports
try:
    import nmap
    NMAP_AVAILABLE = True
except ImportError:
    NMAP_AVAILABLE = False

try:
    import dns.resolver
    import dns.zone
    import dns.query
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False

try:
    import whois
    WHOIS_AVAILABLE = True
except ImportError:
    WHOIS_AVAILABLE = False

try:
    import shodan
    SHODAN_AVAILABLE = True
except ImportError:
    SHODAN_AVAILABLE = False

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

class ScanMode(str, Enum):
    """Scan operation modes"""
    DISCOVERY = "discovery"
    PORT_SCAN = "port_scan"
    SERVICE_DETECT = "service_detect"
    DNS_RECON = "dns_recon"
    SSL_ANALYSIS = "ssl_analysis"
    WEB_TECH = "web_tech"
    SHODAN_LOOKUP = "shodan_lookup"
    FULL = "full"

@dataclass
class NetworkScanConfig:
    """Configuration for network scanning operations"""
    
    # Target specification
    targets: List[str] = field(default_factory=list)
    
    # Host discovery
    ping_timeout: int = 2
    verify_hosts: bool = True
    max_discovery_threads: int = 50
    use_nmap_discovery: bool = False  # Use nmap if available
    
    # Port scanning
    port_ranges: List[str] = field(default_factory=lambda: ["1-1000"])
    scan_timeout: float = 1.0
    max_port_threads: int = 100
    use_nmap_scan: bool = False  # Use nmap if available
    
    # Service detection
    grab_banners: bool = True
    banner_timeout: float = 3.0
    service_version_detection: bool = True
    
    # DNS reconnaissance
    dns_enumeration: bool = False
    subdomain_wordlist: Optional[List[str]] = None
    attempt_zone_transfer: bool = False
    
    # SSL/TLS analysis
    ssl_analysis: bool = False
    check_certificate: bool = True
    check_ssl_issues: bool = True
    
    # Web technology detection
    web_tech_detection: bool = False
    tech_signatures_file: Optional[str] = None
    confidence_threshold: float = 0.3
    
    # Shodan integration
    shodan_lookup: bool = False
    shodan_api_key: Optional[str] = None
    
    # Performance
    rate_limit: Optional[float] = None
    
    # Graph options
    link_to_session: bool = True
    create_topology_map: bool = True
    reuse_existing_nodes: bool = True
    
    # Auto-prerequisite execution
    auto_run_prerequisites: bool = True
    
    @classmethod
    def quick_scan(cls) -> 'NetworkScanConfig':
        return cls(
            port_ranges=["21-23,25,53,80,110,143,443,445,3306,3389,5432,8080"],
            grab_banners=True,
            service_version_detection=True
        )
    
    @classmethod
    def standard_scan(cls) -> 'NetworkScanConfig':
        return cls(
            port_ranges=["1-1000"],
            grab_banners=True,
            service_version_detection=True,
            dns_enumeration=True,
            ssl_analysis=True
        )
    
    @classmethod
    def full_scan(cls) -> 'NetworkScanConfig':
        return cls(
            port_ranges=["1-65535"],
            grab_banners=True,
            service_version_detection=True,
            dns_enumeration=True,
            ssl_analysis=True,
            web_tech_detection=True,
            use_nmap_scan=NMAP_AVAILABLE
        )
    
    @classmethod
    def osint_scan(cls) -> 'NetworkScanConfig':
        """OSINT-focused configuration"""
        return cls(
            dns_enumeration=True,
            ssl_analysis=True,
            web_tech_detection=True,
            shodan_lookup=True,
            attempt_zone_transfer=True
        )

# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class FlexibleTargetInput(BaseModel):
    target: str = Field(description="Target(s): IP, CIDR, hostname, domain, or comma-separated")

class DiscoverHostsInput(FlexibleTargetInput):
    timeout: int = Field(default=2, description="Ping timeout in seconds")
    max_threads: int = Field(default=50, description="Max concurrent checks")
    use_nmap: bool = Field(default=False, description="Use nmap for discovery if available")

class ScanPortsInput(FlexibleTargetInput):
    ports: str = Field(default="1-1000", description="Port spec: '1-1000', '22,80,443'")
    timeout: float = Field(default=1.0, description="Port timeout")
    only_live_hosts: bool = Field(default=True, description="Only scan verified hosts")
    use_nmap: bool = Field(default=False, description="Use nmap for scanning if available")

class DetectServicesInput(FlexibleTargetInput):
    ports: Optional[str] = Field(default=None, description="Specific ports or use discovered")
    grab_banners: bool = Field(default=True, description="Attempt banner grabbing")
    timeout: float = Field(default=3.0, description="Service detection timeout")

class DNSReconInput(BaseModel):
    domain: str = Field(description="Domain to enumerate (e.g., example.com)")
    enumerate_subdomains: bool = Field(default=True, description="Enumerate subdomains")
    attempt_zone_transfer: bool = Field(default=False, description="Attempt DNS zone transfer")
    wordlist: Optional[List[str]] = Field(default=None, description="Custom subdomain wordlist")

class SSLAnalysisInput(BaseModel):
    target: str = Field(description="Hostname to analyze SSL/TLS")
    port: int = Field(default=443, description="SSL port")
    check_issues: bool = Field(default=True, description="Check for security issues")

class WebTechDetectionInput(BaseModel):
    url: str = Field(description="URL to analyze (e.g., https://example.com)")
    signatures_file: Optional[str] = Field(default=None, description="Path to signatures JSON")

class ShodanLookupInput(BaseModel):
    target: str = Field(description="IP address or search query")
    api_key: str = Field(description="Shodan API key")
    lookup_type: str = Field(default="host", description="'host' or 'search'")
    max_results: int = Field(default=10, description="Max search results")

class ComprehensiveScanInput(FlexibleTargetInput):
    scan_type: str = Field(default="standard", description="'quick', 'standard', 'full', 'osint'")
    custom_ports: Optional[str] = Field(default=None, description="Custom port list")
    include_dns: bool = Field(default=False, description="Include DNS enumeration")
    include_ssl: bool = Field(default=False, description="Include SSL analysis")
    include_web_tech: bool = Field(default=False, description="Include web tech detection")
    shodan_api_key: Optional[str] = Field(default=None, description="Shodan API key for lookup")

# =============================================================================
# INPUT PARSER
# =============================================================================

class InputParser:
    """Intelligent input parser for various target formats"""
    
    @staticmethod
    def extract_targets(input_text: str) -> str:
        """Extract clean target specification from potentially formatted input"""
        if not input_text:
            return ""
        
        input_text = str(input_text).strip()
        
        if InputParser._is_clean_target(input_text):
            return input_text
        
        # Extract scan ID
        scan_id_match = re.search(r'scan_(\d+)', input_text)
        if scan_id_match:
            target_match = re.search(r'Target:\s*([^\s\|]+)', input_text)
            if target_match:
                return target_match.group(1).strip()
        
        # Extract IPs
        ips = InputParser._extract_ips_from_text(input_text)
        if ips:
            return ','.join(ips)
        
        # Extract hostnames
        hostnames = InputParser._extract_hostnames_from_text(input_text)
        if hostnames:
            return ','.join(hostnames)
        
        return input_text
    
    @staticmethod
    def _is_clean_target(text: str) -> bool:
        """Check if text is already a clean target spec"""
        try:
            ipaddress.ip_address(text)
            return True
        except ValueError:
            pass
        
        try:
            ipaddress.ip_network(text, strict=False)
            return True
        except ValueError:
            pass
        
        if '-' in text and '.' in text:
            parts = text.split('-')
            if len(parts) == 2:
                try:
                    ipaddress.ip_address(parts[0].strip())
                    return True
                except ValueError:
                    pass
        
        if ',' in text:
            parts = [p.strip() for p in text.split(',')]
            if all(InputParser._is_clean_target(p) for p in parts):
                return True
        
        if re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$', text):
            return True
        
        return False
    
    @staticmethod
    def _extract_ips_from_text(text: str) -> List[str]:
        """Extract all IP addresses from text"""
        ipv4_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
        matches = re.findall(ipv4_pattern, text)
        
        valid_ips = []
        for match in matches:
            try:
                ipaddress.ip_address(match)
                valid_ips.append(match)
            except ValueError:
                continue
        
        return valid_ips
    
    @staticmethod
    def _extract_hostnames_from_text(text: str) -> List[str]:
        """Extract potential hostnames from text"""
        hostname_pattern = r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b'
        matches = re.findall(hostname_pattern, text)
        return list(set(matches))

# =============================================================================
# TARGET PARSER
# =============================================================================

class TargetParser:
    """Parse and expand target specifications"""
    
    @staticmethod
    def parse(target: str) -> List[str]:
        """Parse target into list of IP addresses/hostnames"""
        target = InputParser.extract_targets(target)
        hosts = []
        target = str(target).strip()
        
        if ',' in target:
            for t in target.split(','):
                hosts.extend(TargetParser.parse(t.strip()))
            return list(set(hosts))
        
        if '/' in target:
            try:
                network = ipaddress.ip_network(target, strict=False)
                return [str(ip) for ip in network.hosts()]
            except ValueError:
                pass
        
        if '-' in target and '.' in target:
            try:
                if target.count('.') >= 6:
                    start_ip, end_ip = target.split('-')
                    start = ipaddress.IPv4Address(start_ip.strip())
                    end = ipaddress.IPv4Address(end_ip.strip())
                    return [str(ipaddress.IPv4Address(ip)) 
                            for ip in range(int(start), int(end) + 1)]
                else:
                    base, range_part = target.rsplit('.', 1)
                    if '-' in range_part:
                        start, end = map(int, range_part.split('-'))
                        return [f"{base}.{i}" for i in range(start, end + 1)]
            except (ValueError, ipaddress.AddressValueError):
                pass
        
        try:
            ipaddress.ip_address(target)
            hosts.append(target)
        except ValueError:
            try:
                resolved_ip = socket.gethostbyname(target)
                hosts.append(resolved_ip)
            except socket.gaierror:
                hosts.append(target)
        
        return hosts
    
    @staticmethod
    def parse_ports(port_spec: str) -> List[int]:
        """Parse port specification into list"""
        ports = set()
        
        for part in port_spec.split(','):
            part = part.strip()
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    ports.update(range(start, min(end + 1, 65536)))
                except ValueError:
                    continue
            else:
                try:
                    port = int(part)
                    if 1 <= port <= 65535:
                        ports.add(port)
                except ValueError:
                    continue
        
        return sorted(ports)

# =============================================================================
# HOST DISCOVERY
# =============================================================================

class HostDiscovery:
    """Host discovery and reachability checking"""
    
    def __init__(self, config: NetworkScanConfig):
        self.config = config
        if config.use_nmap_discovery and NMAP_AVAILABLE:
            self.nm = nmap.PortScanner()
        else:
            self.nm = None
    
    def is_host_alive(self, host: str, timeout: int = 2) -> Tuple[bool, Optional[str]]:
        """Check if host is reachable"""
        try:
            result = subprocess.run(
                ['ping', '-c', '1', '-W', str(timeout), host],
                capture_output=True,
                timeout=timeout + 1
            )
            if result.returncode == 0:
                hostname = None
                try:
                    hostname = socket.gethostbyaddr(host)[0]
                except socket.herror:
                    pass
                return True, hostname
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        for port in [80, 443, 22, 21]:
            if self._check_tcp_port(host, port, timeout):
                hostname = None
                try:
                    hostname = socket.gethostbyaddr(host)[0]
                except socket.herror:
                    pass
                return True, hostname
        
        return False, None
    
    def _check_tcp_port(self, host: str, port: int, timeout: float) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            result = sock.connect_ex((host, port))
            return result == 0
        except socket.error:
            return False
        finally:
            sock.close()
    
    def discover_live_hosts(self, targets: List[str]) -> Iterator[Dict[str, Any]]:
        """Discover live hosts"""
        if self.nm and len(targets) > 10:
            # Use nmap for large scans
            yield from self._nmap_discovery(targets)
        else:
            # Use socket-based for small scans
            yield from self._socket_discovery(targets)
    
    def _socket_discovery(self, targets: List[str]) -> Iterator[Dict[str, Any]]:
        """Socket-based host discovery"""
        def check_host(ip):
            alive, hostname = self.is_host_alive(ip, self.config.ping_timeout)
            return {"ip": ip, "hostname": hostname, "alive": alive}
        
        with ThreadPoolExecutor(max_workers=self.config.max_discovery_threads) as executor:
            futures = {executor.submit(check_host, ip): ip for ip in targets}
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result["alive"]:
                        yield result
                except Exception:
                    continue
    
    def _nmap_discovery(self, targets: List[str]) -> Iterator[Dict[str, Any]]:
        """Nmap-based host discovery"""
        try:
            target_str = ' '.join(targets[:256])  # Limit targets
            self.nm.scan(hosts=target_str, arguments="-sn")
            
            for host in self.nm.all_hosts():
                hostname = None
                if 'hostnames' in self.nm[host]:
                    hostnames = self.nm[host]['hostnames']
                    if hostnames and len(hostnames) > 0:
                        hostname = hostnames[0].get('name', '')
                
                yield {
                    "ip": host,
                    "hostname": hostname,
                    "alive": True,
                    "method": "nmap"
                }
        except Exception as e:
            logger.error(f"Nmap discovery failed: {e}")

# =============================================================================
# PORT SCANNER
# =============================================================================

class PortScanner:
    """Port scanning functionality"""
    
    def __init__(self, config: NetworkScanConfig):
        self.config = config
        if config.use_nmap_scan and NMAP_AVAILABLE:
            self.nm = nmap.PortScanner()
        else:
            self.nm = None
        
        self.common_ports = {
            21: 'FTP', 22: 'SSH', 23: 'Telnet', 25: 'SMTP', 53: 'DNS',
            80: 'HTTP', 110: 'POP3', 143: 'IMAP', 443: 'HTTPS',
            445: 'SMB', 3306: 'MySQL', 3389: 'RDP', 5432: 'PostgreSQL',
            5900: 'VNC', 6379: 'Redis', 8080: 'HTTP-Alt', 8443: 'HTTPS-Alt',
            9200: 'Elasticsearch', 27017: 'MongoDB'
        }
    
    def scan_host(self, host: str, ports: List[int]) -> Iterator[Dict[str, Any]]:
        """Scan ports on host"""
        if self.nm and len(ports) > 100:
            # Use nmap for large port ranges
            yield from self._nmap_scan(host, ports)
        else:
            # Use socket for targeted scans
            yield from self._socket_scan(host, ports)
    
    def _socket_scan(self, host: str, ports: List[int]) -> Iterator[Dict[str, Any]]:
        """Socket-based port scanning"""
        def check_port(port):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.config.scan_timeout)
            try:
                result = sock.connect_ex((host, port))
                if result == 0:
                    return {
                        "port": port,
                        "state": "open",
                        "service": self.common_ports.get(port, f"unknown-{port}")
                    }
            except socket.error:
                pass
            finally:
                sock.close()
            return None
        
        with ThreadPoolExecutor(max_workers=self.config.max_port_threads) as executor:
            futures = {executor.submit(check_port, port): port for port in ports}
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        yield result
                except Exception:
                    continue
    
    def _nmap_scan(self, host: str, ports: List[int]) -> Iterator[Dict[str, Any]]:
        """Nmap-based port scanning"""
        try:
            port_str = ','.join(map(str, ports[:1000]))  # Limit ports
            self.nm.scan(hosts=host, ports=port_str, arguments="-sV")
            
            if host in self.nm.all_hosts():
                for proto in self.nm[host].all_protocols():
                    ports_info = self.nm[host][proto]
                    
                    for port, info in ports_info.items():
                        if info.get('state') == 'open':
                            yield {
                                "port": port,
                                "state": "open",
                                "service": info.get('name', 'unknown'),
                                "product": info.get('product', ''),
                                "version": info.get('version', ''),
                                "method": "nmap"
                            }
        except Exception as e:
            logger.error(f"Nmap scan failed: {e}")

# =============================================================================
# SERVICE DETECTOR
# =============================================================================

class ServiceDetector:
    """Service detection and banner grabbing"""
    
    def __init__(self, config: NetworkScanConfig):
        self.config = config
        self.service_signatures = {
            'SSH': [b'SSH-', b'OpenSSH'],
            'HTTP': [b'HTTP/', b'<html', b'<HTML'],
            'FTP': [b'220', b'FTP'],
            'SMTP': [b'220', b'ESMTP'],
            'MySQL': [b'mysql', b'MariaDB'],
            'PostgreSQL': [b'postgres'],
            'Redis': [b'REDIS', b'-ERR'],
            'MongoDB': [b'MongoDB'],
        }
    
    def detect_service(self, host: str, port: int) -> Dict[str, Any]:
        """Detect service on port"""
        result = {
            "service": f"unknown-{port}",
            "version": None,
            "banner": None,
            "confidence": "low"
        }
        
        if not self.config.grab_banners:
            return result
        
        banner = self._grab_banner(host, port)
        if not banner:
            return result
        
        result["banner"] = banner
        service, version = self._identify_service(banner, port)
        if service:
            result["service"] = service
            result["version"] = version
            result["confidence"] = "high" if version else "medium"
        
        return result
    
    def _grab_banner(self, host: str, port: int) -> Optional[str]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.config.banner_timeout)
        
        try:
            sock.connect((host, port))
            if port in [80, 8080, 8000, 8888, 5000]:
                sock.send(b"GET / HTTP/1.0\r\nHost: " + host.encode() + b"\r\n\r\n")
            
            banner = sock.recv(4096)
            return banner.decode('utf-8', errors='ignore').strip()
        except socket.error:
            return None
        finally:
            sock.close()
    
    def _identify_service(self, banner: str, port: int) -> Tuple[Optional[str], Optional[str]]:
        banner_lower = banner.lower()
        
        for service, signatures in self.service_signatures.items():
            if any(sig.decode('utf-8', errors='ignore').lower() in banner_lower 
                   for sig in signatures):
                version = self._extract_version(banner)
                return service, version
        
        return None, None
    
    def _extract_version(self, banner: str) -> Optional[str]:
        patterns = [
            r'(\d+\.\d+\.\d+)',
            r'(\d+\.\d+)',
            r'version[:\s]+([^\s\)]+)',
            r'v(\d+\.\d+[^\s]*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, banner, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None

# =============================================================================
# DNS RECONNAISSANCE
# =============================================================================

class DNSRecon:
    """DNS enumeration and reconnaissance"""
    
    def __init__(self, config: NetworkScanConfig):
        self.config = config
        if not DNS_AVAILABLE:
            raise ImportError("dnspython required. Install: pip install dnspython")
        self.resolver = dns.resolver.Resolver()
    
    def enumerate_dns(self, domain: str) -> Dict[str, Any]:
        """Comprehensive DNS enumeration"""
        logger.info(f"DNS enumeration: {domain}")
        
        result = {
            "domain": domain,
            "a_records": [],
            "nameservers": [],
            "mx_records": [],
            "txt_records": [],
            "subdomains": [],
            "registrar": None,
            "creation_date": None,
            "expiration_date": None
        }
        
        # A records
        try:
            answers = self.resolver.resolve(domain, 'A')
            result["a_records"] = [str(rdata) for rdata in answers]
        except:
            pass
        
        # NS records
        try:
            answers = self.resolver.resolve(domain, 'NS')
            result["nameservers"] = [str(rdata) for rdata in answers]
        except:
            pass
        
        # MX records
        try:
            answers = self.resolver.resolve(domain, 'MX')
            result["mx_records"] = [f"{rdata.preference} {rdata.exchange}" for rdata in answers]
        except:
            pass
        
        # TXT records
        try:
            answers = self.resolver.resolve(domain, 'TXT')
            result["txt_records"] = [str(rdata) for rdata in answers]
        except:
            pass
        
        # WHOIS
        if WHOIS_AVAILABLE:
            try:
                w = whois.whois(domain)
                result["registrar"] = w.registrar
                if w.creation_date:
                    if isinstance(w.creation_date, list):
                        result["creation_date"] = str(w.creation_date[0])
                    else:
                        result["creation_date"] = str(w.creation_date)
                if w.expiration_date:
                    if isinstance(w.expiration_date, list):
                        result["expiration_date"] = str(w.expiration_date[0])
                    else:
                        result["expiration_date"] = str(w.expiration_date)
            except:
                pass
        
        return result
    
    def enumerate_subdomains(self, domain: str, wordlist: Optional[List[str]] = None) -> List[str]:
        """Subdomain enumeration via brute force"""
        if wordlist is None:
            wordlist = [
                'www', 'mail', 'ftp', 'localhost', 'webmail', 'smtp', 'pop', 'ns1',
                'ns2', 'cpanel', 'whm', 'autodiscover', 'autoconfig', 'm', 'imap',
                'test', 'ns', 'blog', 'pop3', 'dev', 'www2', 'admin', 'forum',
                'news', 'vpn', 'ns3', 'mail2', 'new', 'mysql', 'old', 'lists',
                'support', 'mobile', 'mx', 'static', 'docs', 'beta', 'shop', 'sql',
                'secure', 'demo', 'cp', 'calendar', 'wiki', 'web', 'media', 'email',
                'images', 'img', 'www1', 'intranet', 'portal', 'video', 'sip',
                'dns2', 'api', 'cdn', 'stats', 'dns1', 'ns4', 'www3', 'dns',
                'search', 'staging', 'server', 'mx1', 'chat', 'wap', 'my', 'svn',
                'mail1', 'sites', 'proxy', 'ads', 'host', 'crm', 'cms', 'backup'
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
        """Attempt DNS zone transfer (AXFR)"""
        logger.info(f"Attempting zone transfer for {domain}")
        
        records = []
        
        try:
            ns_answers = self.resolver.resolve(domain, 'NS')
            nameservers = [str(rdata) for rdata in ns_answers]
            
            for ns in nameservers:
                try:
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
        """Reverse DNS lookup"""
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return hostname
        except:
            return None

# =============================================================================
# SSL/TLS ANALYZER
# =============================================================================

class SSLAnalyzer:
    """SSL/TLS certificate and configuration analysis"""
    
    def __init__(self, config: NetworkScanConfig):
        self.config = config
    
    def analyze_ssl(self, hostname: str, port: int = 443) -> Dict[str, Any]:
        """Analyze SSL/TLS certificate and configuration"""
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
                    
                    result["protocol_versions"] = [version]
                    
                    if cipher:
                        result["ciphers"] = [{
                            "name": cipher[0],
                            "protocol": cipher[1],
                            "bits": cipher[2]
                        }]
                    
                    if self.config.check_ssl_issues:
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
# WEB TECHNOLOGY DETECTOR
# =============================================================================

class WebTechDetector:
    """Web technology fingerprinting"""
    
    def __init__(self, config: NetworkScanConfig):
        self.config = config
        self.signatures = self._load_signatures(config.tech_signatures_file)
        self.confidence_threshold = config.confidence_threshold
    
    def _load_signatures(self, file_path: Optional[str]) -> Dict[str, Any]:
        """Load technology signatures from JSON file"""
        if file_path is None:
            file_path = Path(__file__).parent / "tech_signatures.json"
        
        signatures = {}
        
        if file_path and Path(file_path).exists():
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    signatures = data.get('technologies', {})
                    logger.info(f"Loaded {len(signatures)} technology signatures")
            except Exception as e:
                logger.error(f"Failed to load signatures: {e}")
        
        # Fallback built-in signatures
        if not signatures:
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
                },
                "Apache": {
                    "category": "Web Server",
                    "patterns": {
                        "headers": {"Server": "Apache"}
                    }
                }
            }
        
        return signatures
    
    def detect(self, url: str) -> List[Dict[str, Any]]:
        """Detect technologies used by a website"""
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
                
                # Add technology if confidence exceeds threshold
                if evidence and confidence >= self.confidence_threshold:
                    tech = {
                        "name": tech_name,
                        "category": sig.get('category', 'unknown'),
                        "confidence": min(confidence, 1.0),
                        "evidence": evidence[:5]
                    }
                    
                    # Try to extract version
                    version = self._extract_version_from_pattern(
                        html, headers, scripts, sig.get('version_pattern', '')
                    )
                    if version:
                        tech["version"] = version
                    
                    technologies.append(tech)
            
            # Sort by confidence
            technologies.sort(key=lambda t: t['confidence'], reverse=True)
            
            logger.info(f"Detected {len(technologies)} technologies")
            
        except Exception as e:
            logger.error(f"Technology detection failed: {e}")
        
        return technologies
    
    def _extract_version_from_pattern(self, html: str, headers: Dict, 
                                     scripts: List[str], version_pattern: str) -> Optional[str]:
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
# SHODAN CLIENT
# =============================================================================

class ShodanClient:
    """Shodan integration for passive reconnaissance"""
    
    def __init__(self, config: NetworkScanConfig):
        self.config = config
        if not SHODAN_AVAILABLE:
            raise ImportError("shodan required. Install: pip install shodan")
        
        if not config.shodan_api_key:
            raise ValueError("Shodan API key required")
        
        self.api = shodan.Shodan(config.shodan_api_key)
    
    def search_host(self, ip: str) -> Dict[str, Any]:
        """Lookup host in Shodan database"""
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
        """Search Shodan using custom query"""
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
# NETWORK MAPPER - MAIN ORCHESTRATOR
# =============================================================================

class NetworkMapper:
    """Network mapper with comprehensive OSINT capabilities"""
    
    def __init__(self, agent, config: NetworkScanConfig):
        self.agent = agent
        self.config = config
        
        self.target_parser = TargetParser()
        self.host_discovery = HostDiscovery(config)
        self.port_scanner = PortScanner(config)
        self.service_detector = ServiceDetector(config)
        
        # Optional components
        self.dns_recon = None
        self.ssl_analyzer = None
        self.web_tech_detector = None
        self.shodan_client = None
        
        if config.dns_enumeration and DNS_AVAILABLE:
            self.dns_recon = DNSRecon(config)
        
        if config.ssl_analysis:
            self.ssl_analyzer = SSLAnalyzer(config)
        
        if config.web_tech_detection:
            self.web_tech_detector = WebTechDetector(config)
        
        if config.shodan_lookup and config.shodan_api_key and SHODAN_AVAILABLE:
            try:
                self.shodan_client = ShodanClient(config)
            except Exception as e:
                logger.warning(f"Shodan initialization failed: {e}")
        
        self.scan_node_id = None
        self.discovered_ips = {}
        self.discovered_ports = {}
        self.discovered_services = {}
    
    def _initialize_scan(self, tool_name: str, targets: str):
        """Initialize scan context"""
        if self.scan_node_id is not None:
            return
        
        try:
            scan_mem = self.agent.mem.add_session_memory(
                self.agent.sess.id,
                targets,
                "network_scan",
                metadata={
                    "tool": tool_name,
                    "targets": targets,
                    "started_at": datetime.now().isoformat(),
                }
            )
            self.scan_node_id = scan_mem.id
        except Exception:
            pass
    
    def _create_ip_node(self, ip: str, hostname: Optional[str] = None) -> str:
        """Create or reuse IP node"""
        if ip in self.discovered_ips:
            return self.discovered_ips[ip]
        
        node_id = f"ip_{ip.replace('.', '_')}"
        
        properties = {
            "ip_address": ip,
            "status": "up",
            "discovered_at": datetime.now().isoformat(),
        }
        
        if hostname:
            properties["hostname"] = hostname
        
        try:
            self.agent.mem.upsert_entity(
                node_id,
                "network_host",
                labels=["NetworkHost", "IP"],
                properties=properties
            )
            
            if self.scan_node_id:
                self.agent.mem.link(
                    self.scan_node_id,
                    node_id,
                    "DISCOVERED_IP",
                    {"ip": ip}
                )
        except Exception:
            pass
        
        self.discovered_ips[ip] = node_id
        return node_id
    
    def _create_port_node(self, ip_node_id: str, ip: str, port: int, state: str = "open") -> str:
        """Create or reuse port node"""
        cache_key = (ip, port)
        
        if cache_key in self.discovered_ports:
            return self.discovered_ports[cache_key]
        
        port_node_id = f"{ip_node_id}_port_{port}"
        
        try:
            self.agent.mem.upsert_entity(
                port_node_id,
                "network_port",
                labels=["NetworkPort", "Port"],
                properties={
                    "port_number": port,
                    "protocol": "tcp",
                    "state": state,
                    "discovered_at": datetime.now().isoformat(),
                }
            )
            
            self.agent.mem.link(
                ip_node_id,
                port_node_id,
                "HAS_PORT",
                {"port": port, "state": state}
            )
            
            if self.scan_node_id:
                self.agent.mem.link(
                    self.scan_node_id,
                    port_node_id,
                    "FOUND_PORT",
                    {"port": port, "ip": ip}
                )
        except Exception:
            pass
        
        self.discovered_ports[cache_key] = port_node_id
        return port_node_id
    
    def _create_service_node(self, port_node_id: str, ip: str, port: int,
                            service_data: Dict[str, Any]) -> str:
        """Create or update service node"""
        service_node_id = f"{port_node_id}_service"
        
        try:
            properties = {
                "service_name": service_data["service"],
                "confidence": service_data["confidence"],
                "discovered_at": datetime.now().isoformat(),
            }
            
            if service_data.get("version"):
                properties["version"] = service_data["version"]
            if service_data.get("banner"):
                properties["banner"] = service_data["banner"][:500]
            
            self.agent.mem.upsert_entity(
                service_node_id,
                "network_service",
                labels=["NetworkService", "Service"],
                properties=properties
            )
            
            self.agent.mem.link(
                port_node_id,
                service_node_id,
                "RUNS_SERVICE",
                {"service": service_data["service"]}
            )
            
            if self.scan_node_id:
                self.agent.mem.link(
                    self.scan_node_id,
                    service_node_id,
                    "IDENTIFIED_SERVICE",
                    {
                        "service": service_data["service"],
                        "version": service_data.get("version"),
                        "ip": ip,
                        "port": port
                    }
                )
        except Exception:
            pass
        
        self.discovered_services[(ip, port)] = (service_node_id, service_data)
        return service_node_id
    
    # =========================================================================
    # SCAN OPERATIONS
    # =========================================================================
    
    def discover_hosts(self, target: str, timeout: int = 2, use_nmap: bool = False) -> Iterator[str]:
        """Host discovery"""
        self._initialize_scan("discover_hosts", target)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                     HOST DISCOVERY                           ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        targets = self.target_parser.parse(target)
        yield f"Checking {len(targets)} target(s)...\n\n"
        
        live_count = 0
        
        for host_info in self.host_discovery.discover_live_hosts(targets):
            if host_info["alive"]:
                live_count += 1
                ip = host_info["ip"]
                hostname = host_info["hostname"]
                
                self._create_ip_node(ip, hostname)
                
                yield f"  [✓] {ip}"
                if hostname:
                    yield f" ({hostname})"
                yield f"\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Live Hosts: {live_count}/{len(targets)}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def scan_ports(self, target: str, ports: str = "1-1000",
                   timeout: float = 1.0, only_live_hosts: bool = True,
                   use_nmap: bool = False) -> Iterator[str]:
        """Port scanning"""
        self._initialize_scan("scan_ports", target)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                      PORT SCANNING                           ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        targets = self.target_parser.parse(target)
        port_list = self.target_parser.parse_ports(ports)
        
        yield f"Targets: {len(targets)}\n"
        yield f"Ports: {len(port_list)}\n\n"
        
        total_open = 0
        
        for ip in targets:
            if only_live_hosts:
                alive, hostname = self.host_discovery.is_host_alive(ip)
                if not alive:
                    continue
            else:
                hostname = None
            
            ip_node_id = self._create_ip_node(ip, hostname)
            
            yield f"\n  [•] Scanning {ip}...\n"
            
            port_count = 0
            for port_info in self.port_scanner.scan_host(ip, port_list):
                port_count += 1
                total_open += 1
                
                self._create_port_node(
                    ip_node_id, ip, port_info["port"], port_info["state"]
                )
                
                yield f"      [✓] Port {port_info['port']}: {port_info['service']}\n"
            
            if port_count == 0:
                yield f"      No open ports found\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Total Open Ports: {total_open}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def detect_services(self, target: str, ports: Optional[str] = None,
                       grab_banners: bool = True) -> Iterator[str]:
        """Service detection"""
        self._initialize_scan("detect_services", target)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                   SERVICE DETECTION                          ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        targets = self.target_parser.parse(target)
        
        if not self.discovered_ports and not ports and self.config.auto_run_prerequisites:
            yield f"  [!] No ports found - auto-scanning common ports...\n\n"
            
            for chunk in self.scan_ports(target, "21-23,25,53,80,110,143,443,445,3306,3389,5432,8080", only_live_hosts=True):
                if not chunk.startswith("╔"):
                    yield chunk
            
            yield f"\n  [•] Continuing with service detection...\n\n"
        
        services_found = 0
        
        for ip in targets:
            if ip not in self.discovered_ips:
                ip_node_id = self._create_ip_node(ip)
            else:
                ip_node_id = self.discovered_ips[ip]
            
            if ports:
                open_ports = self.target_parser.parse_ports(ports)
            else:
                open_ports = [p for (i, p) in self.discovered_ports.keys() if i == ip]
            
            if not open_ports:
                continue
            
            yield f"\n  [•] Detecting services on {ip}...\n"
            
            for port in open_ports:
                port_node_id = self.discovered_ports.get((ip, port))
                if not port_node_id:
                    port_node_id = self._create_port_node(ip_node_id, ip, port)
                
                service_data = self.service_detector.detect_service(ip, port)
                
                self._create_service_node(port_node_id, ip, port, service_data)
                services_found += 1
                
                yield f"      [✓] Port {port}: {service_data['service']}"
                if service_data.get("version"):
                    yield f" {service_data['version']}"
                yield f" ({service_data['confidence']} confidence)\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Services Detected: {services_found}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def enumerate_dns(self, domain: str, enumerate_subdomains: bool = True,
                     attempt_zone_transfer: bool = False,
                     wordlist: Optional[List[str]] = None) -> Iterator[str]:
        """DNS reconnaissance"""
        if not self.dns_recon:
            yield "DNS enumeration not available (dnspython not installed)\n"
            return
        
        self._initialize_scan("enumerate_dns", domain)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                   DNS RECONNAISSANCE                         ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        yield f"  Domain: {domain}\n\n"
        
        # Basic DNS enumeration
        yield "  [•] Enumerating DNS records...\n"
        dns_data = self.dns_recon.enumerate_dns(domain)
        
        if dns_data.get("a_records"):
            yield f"\n  A Records:\n"
            for record in dns_data["a_records"]:
                yield f"    • {record}\n"
        
        if dns_data.get("nameservers"):
            yield f"\n  Nameservers:\n"
            for ns in dns_data["nameservers"]:
                yield f"    • {ns}\n"
        
        if dns_data.get("mx_records"):
            yield f"\n  MX Records:\n"
            for mx in dns_data["mx_records"]:
                yield f"    • {mx}\n"
        
        if dns_data.get("txt_records"):
            yield f"\n  TXT Records:\n"
            for txt in dns_data["txt_records"][:5]:
                yield f"    • {txt[:100]}\n"
        
        if dns_data.get("registrar"):
            yield f"\n  Registrar: {dns_data['registrar']}\n"
        
        # Subdomain enumeration
        if enumerate_subdomains:
            yield f"\n  [•] Enumerating subdomains...\n"
            subdomains = self.dns_recon.enumerate_subdomains(domain, wordlist)
            
            if subdomains:
                yield f"\n  Discovered Subdomains ({len(subdomains)}):\n"
                for subdomain in subdomains[:20]:
                    yield f"    • {subdomain}\n"
                
                if len(subdomains) > 20:
                    yield f"    ... and {len(subdomains) - 20} more\n"
        
        # Zone transfer attempt
        if attempt_zone_transfer:
            yield f"\n  [•] Attempting zone transfer...\n"
            records = self.dns_recon.dns_zone_transfer(domain)
            
            if records:
                yield f"  [!] Zone transfer successful! ({len(records)} records)\n"
                for record in records[:10]:
                    yield f"    • {record}\n"
            else:
                yield f"  Zone transfer not allowed\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  DNS Enumeration Complete\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def analyze_ssl(self, target: str, port: int = 443, check_issues: bool = True) -> Iterator[str]:
        """SSL/TLS analysis"""
        if not self.ssl_analyzer:
            yield "SSL analysis not available\n"
            return
        
        self._initialize_scan("analyze_ssl", f"{target}:{port}")
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                   SSL/TLS ANALYSIS                           ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        yield f"  Target: {target}:{port}\n\n"
        
        result = self.ssl_analyzer.analyze_ssl(target, port)
        
        if result.get("error"):
            yield f"  [!] Error: {result['error']}\n"
            return
        
        cert = result.get("certificate", {})
        
        if cert:
            yield f"  Certificate Information:\n"
            
            subject = cert.get("subject", {})
            if subject:
                yield f"    Subject: {subject.get('commonName', 'N/A')}\n"
            
            issuer = cert.get("issuer", {})
            if issuer:
                yield f"    Issuer: {issuer.get('commonName', 'N/A')}\n"
            
            yield f"    Valid From: {cert.get('notBefore', 'N/A')}\n"
            yield f"    Valid Until: {cert.get('notAfter', 'N/A')}\n"
            
            san = cert.get("subjectAltName", [])
            if san:
                yield f"\n    Subject Alternative Names:\n"
                for name in san[:5]:
                    yield f"      • {name[1]}\n"
        
        versions = result.get("protocol_versions", [])
        if versions:
            yield f"\n  Protocol: {', '.join(versions)}\n"
        
        ciphers = result.get("ciphers", [])
        if ciphers:
            yield f"  Cipher Suite: {ciphers[0].get('name')}\n"
        
        issues = result.get("issues", [])
        if issues:
            yield f"\n  [!] Security Issues:\n"
            for issue in issues:
                yield f"    • {issue}\n"
        else:
            yield f"\n  [✓] No security issues detected\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  SSL/TLS Analysis Complete\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def detect_web_technologies(self, url: str) -> Iterator[str]:
        """Web technology detection"""
        if not self.web_tech_detector:
            yield "Web technology detection not available\n"
            return
        
        self._initialize_scan("detect_web_technologies", url)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                WEB TECHNOLOGY DETECTION                      ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        yield f"  URL: {url}\n\n"
        
        technologies = self.web_tech_detector.detect(url)
        
        if not technologies:
            yield "  No technologies detected\n"
            return
        
        # Group by category
        by_category = {}
        for tech in technologies:
            category = tech.get('category', 'Unknown')
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(tech)
        
        for category, techs in by_category.items():
            yield f"\n  {category}:\n"
            for tech in techs:
                yield f"    • {tech['name']}"
                if tech.get('version'):
                    yield f" {tech['version']}"
                yield f" (confidence: {tech['confidence']:.0%})\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Technologies Detected: {len(technologies)}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def shodan_lookup(self, target: str, lookup_type: str = "host",
                     max_results: int = 10) -> Iterator[str]:
        """Shodan passive reconnaissance"""
        if not self.shodan_client:
            yield "Shodan lookup not available (API key required)\n"
            return
        
        self._initialize_scan("shodan_lookup", target)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                    SHODAN LOOKUP                             ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        if lookup_type == "host":
            # Host lookup
            yield f"  Looking up IP: {target}\n\n"
            
            data = self.shodan_client.search_host(target)
            
            if not data:
                yield "  No data found\n"
                return
            
            yield f"  Organization: {data.get('org', 'Unknown')}\n"
            yield f"  OS: {data.get('os', 'Unknown')}\n"
            
            ports = data.get('ports', [])
            if ports:
                yield f"\n  Open Ports: {', '.join(map(str, ports[:20]))}\n"
            
            hostnames = data.get('hostnames', [])
            if hostnames:
                yield f"  Hostnames: {', '.join(hostnames[:5])}\n"
            
            vulns = data.get('vulns', [])
            if vulns:
                yield f"\n  [!] Known Vulnerabilities ({len(vulns)}):\n"
                for vuln in vulns[:10]:
                    yield f"    • {vuln}\n"
            
            services = data.get('services', [])
            if services:
                yield f"\n  Services:\n"
                for svc in services[:10]:
                    yield f"    • Port {svc['port']}: {svc.get('product', 'unknown')}\n"
        
        else:
            # Search query
            yield f"  Search query: {target}\n\n"
            
            results = self.shodan_client.search_query(target, max_results)
            
            if not results:
                yield "  No results found\n"
                return
            
            for result in results:
                yield f"\n  {result['ip']}:{result['port']}\n"
                yield f"    Org: {result.get('org', 'Unknown')}\n"
                yield f"    Product: {result.get('product', 'Unknown')}\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Shodan Lookup Complete\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def comprehensive_scan(self, target: str, scan_type: str = "standard",
                          custom_ports: Optional[str] = None,
                          include_dns: bool = False,
                          include_ssl: bool = False,
                          include_web_tech: bool = False,
                          shodan_api_key: Optional[str] = None) -> Iterator[str]:
        """Full comprehensive scan"""
        self._initialize_scan("comprehensive_scan", target)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║              COMPREHENSIVE NETWORK SCAN                      ║\n"
        yield f"║                  Mode: {scan_type.upper():^30}              ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        if scan_type == "quick":
            ports = "21-23,25,53,80,110,143,443,445,3306,3389,5432,8080"
        elif scan_type == "standard":
            ports = "1-1000"
        elif scan_type == "full":
            ports = "1-65535"
        elif scan_type == "osint":
            ports = "80,443,8080,8443"
            include_dns = True
            include_ssl = True
            include_web_tech = True
        elif scan_type == "custom" and custom_ports:
            ports = custom_ports
        else:
            ports = "1-1000"
        
        # Parse targets
        targets = self.target_parser.parse(target)
        
        # Check if target is domain for DNS/SSL/web
        is_domain = not any(
            InputParser._is_clean_target(t) and '.' in t and all(c.isdigit() or c == '.' for c in t)
            for t in targets
        )
        
        # DNS enumeration (if domain)
        if include_dns and is_domain and self.dns_recon:
            yield f"[1] DNS RECONNAISSANCE\n{'─' * 60}\n"
            for chunk in self.enumerate_dns(target, enumerate_subdomains=True):
                if not chunk.startswith("╔"):
                    yield chunk
        
        # Host discovery
        step = 2 if include_dns else 1
        yield f"\n[{step}] HOST DISCOVERY\n{'─' * 60}\n"
        for chunk in self.discover_hosts(target):
            if not chunk.startswith("╔"):
                yield chunk
        
        # Port scanning
        step += 1
        yield f"\n[{step}] PORT SCANNING\n{'─' * 60}\n"
        live_hosts = list(self.discovered_ips.keys())
        if live_hosts:
            for chunk in self.scan_ports(",".join(live_hosts), ports, only_live_hosts=False):
                if not chunk.startswith("╔"):
                    yield chunk
        else:
            yield "No live hosts found\n"
        
        # Service detection
        step += 1
        yield f"\n[{step}] SERVICE DETECTION\n{'─' * 60}\n"
        if self.discovered_ports:
            for chunk in self.detect_services(",".join(live_hosts)):
                if not chunk.startswith("╔"):
                    yield chunk
        else:
            yield "No open ports found\n"
        
        # SSL analysis (if applicable)
        if include_ssl and self.ssl_analyzer:
            step += 1
            yield f"\n[{step}] SSL/TLS ANALYSIS\n{'─' * 60}\n"
            
            # Analyze SSL on HTTPS ports
            for ip, port in self.discovered_ports.keys():
                if port in [443, 8443]:
                    for chunk in self.analyze_ssl(ip, port):
                        if not chunk.startswith("╔"):
                            yield chunk
        
        # Web technology detection (if applicable)
        if include_web_tech and self.web_tech_detector:
            step += 1
            yield f"\n[{step}] WEB TECHNOLOGY DETECTION\n{'─' * 60}\n"
            
            # Detect on HTTP/HTTPS ports
            for ip, port in self.discovered_ports.keys():
                if port in [80, 443, 8080, 8443]:
                    protocol = "https" if port in [443, 8443] else "http"
                    url = f"{protocol}://{ip}:{port}"
                    
                    for chunk in self.detect_web_technologies(url):
                        if not chunk.startswith("╔"):
                            yield chunk
        
        # Shodan lookup (if API key provided)
        if shodan_api_key and SHODAN_AVAILABLE:
            step += 1
            yield f"\n[{step}] SHODAN PASSIVE RECONNAISSANCE\n{'─' * 60}\n"
            
            # Temporarily set API key
            original_key = self.config.shodan_api_key
            self.config.shodan_api_key = shodan_api_key
            
            try:
                self.shodan_client = ShodanClient(self.config)
                
                for ip in live_hosts[:5]:  # Limit Shodan lookups
                    for chunk in self.shodan_lookup(ip):
                        if not chunk.startswith("╔"):
                            yield chunk
            except Exception as e:
                yield f"  Shodan lookup failed: {e}\n"
            finally:
                self.config.shodan_api_key = original_key
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                     SCAN COMPLETE                            ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
        yield f"  Live Hosts:     {len(self.discovered_ips)}\n"
        yield f"  Open Ports:     {len(self.discovered_ports)}\n"
        yield f"  Services:       {len(self.discovered_services)}\n"

# =============================================================================
# TOOL INTEGRATION
# =============================================================================

def add_network_scanning_tools(tool_list: List, agent):
    """Add comprehensive network scanning tools"""
    from langchain_core.tools import StructuredTool
    
    def discover_hosts_wrapper(target: str, timeout: int = 2, max_threads: int = 50,
                              use_nmap: bool = False):
        config = NetworkScanConfig(
            ping_timeout=timeout,
            max_discovery_threads=max_threads,
            use_nmap_discovery=use_nmap and NMAP_AVAILABLE,
            auto_run_prerequisites=True
        )
        mapper = NetworkMapper(agent, config)
        for chunk in mapper.discover_hosts(target, timeout, use_nmap):
            yield chunk
    
    def scan_ports_wrapper(target: str, ports: str = "1-1000", 
                          timeout: float = 1.0, only_live_hosts: bool = True,
                          use_nmap: bool = False):
        config = NetworkScanConfig(
            port_ranges=[ports],
            scan_timeout=timeout,
            use_nmap_scan=use_nmap and NMAP_AVAILABLE,
            auto_run_prerequisites=True
        )
        mapper = NetworkMapper(agent, config)
        for chunk in mapper.scan_ports(target, ports, timeout, only_live_hosts, use_nmap):
            yield chunk
    
    def detect_services_wrapper(target: str, ports: Optional[str] = None,
                               grab_banners: bool = True, timeout: float = 3.0):
        config = NetworkScanConfig(
            grab_banners=grab_banners,
            banner_timeout=timeout,
            auto_run_prerequisites=True
        )
        mapper = NetworkMapper(agent, config)
        for chunk in mapper.detect_services(target, ports, grab_banners):
            yield chunk
    
    def enumerate_dns_wrapper(domain: str, enumerate_subdomains: bool = True,
                             attempt_zone_transfer: bool = False,
                             wordlist: Optional[List[str]] = None):
        if not DNS_AVAILABLE:
            yield "DNS enumeration requires dnspython: pip install dnspython\n"
            return
        
        config = NetworkScanConfig(dns_enumeration=True, attempt_zone_transfer=attempt_zone_transfer)
        mapper = NetworkMapper(agent, config)
        for chunk in mapper.enumerate_dns(domain, enumerate_subdomains, 
                                          attempt_zone_transfer, wordlist):
            yield chunk
    
    def analyze_ssl_wrapper(target: str, port: int = 443, check_issues: bool = True):
        config = NetworkScanConfig(ssl_analysis=True, check_ssl_issues=check_issues)
        mapper = NetworkMapper(agent, config)
        for chunk in mapper.analyze_ssl(target, port, check_issues):
            yield chunk
    
    def detect_web_tech_wrapper(url: str, signatures_file: Optional[str] = None):
        config = NetworkScanConfig(
            web_tech_detection=True,
            tech_signatures_file=signatures_file
        )
        mapper = NetworkMapper(agent, config)
        for chunk in mapper.detect_web_technologies(url):
            yield chunk
    
    def shodan_lookup_wrapper(target: str, api_key: str, lookup_type: str = "host",
                             max_results: int = 10):
        if not SHODAN_AVAILABLE:
            yield "Shodan lookup requires shodan: pip install shodan\n"
            return
        
        config = NetworkScanConfig(shodan_lookup=True, shodan_api_key=api_key)
        mapper = NetworkMapper(agent, config)
        for chunk in mapper.shodan_lookup(target, lookup_type, max_results):
            yield chunk
    
    def comprehensive_scan_wrapper(target: str, scan_type: str = "standard",
                                  custom_ports: Optional[str] = None,
                                  include_dns: bool = False,
                                  include_ssl: bool = False,
                                  include_web_tech: bool = False,
                                  shodan_api_key: Optional[str] = None):
        if scan_type == "quick":
            config = NetworkScanConfig.quick_scan()
        elif scan_type == "full":
            config = NetworkScanConfig.full_scan()
        elif scan_type == "osint":
            config = NetworkScanConfig.osint_scan()
        else:
            config = NetworkScanConfig.standard_scan()
        
        config.auto_run_prerequisites = True
        config.dns_enumeration = include_dns
        config.ssl_analysis = include_ssl
        config.web_tech_detection = include_web_tech
        
        if shodan_api_key:
            config.shodan_lookup = True
            config.shodan_api_key = shodan_api_key
        
        mapper = NetworkMapper(agent, config)
        for chunk in mapper.comprehensive_scan(
            target, scan_type, custom_ports, include_dns, 
            include_ssl, include_web_tech, shodan_api_key
        ):
            yield chunk
    
    tool_list.extend([
        StructuredTool.from_function(
            func=discover_hosts_wrapper,
            name="discover_hosts",
            description=(
                "Discover live hosts on network. Supports nmap for large scans. "
                "Accepts IPs, CIDRs, hostnames, or formatted output from other tools."
            ),
            args_schema=DiscoverHostsInput
        ),
        
        StructuredTool.from_function(
            func=scan_ports_wrapper,
            name="scan_ports",
            description=(
                "Scan ports on targets. Supports nmap for enhanced scanning. "
                "Accepts IPs, CIDRs, or formatted output. Tool chaining compatible."
            ),
            args_schema=ScanPortsInput
        ),
        
        StructuredTool.from_function(
            func=detect_services_wrapper,
            name="detect_services",
            description=(
                "Detect services with banner grabbing. FULLY STANDALONE. "
                "Automatically scans ports if none exist. Tool chaining compatible."
            ),
            args_schema=DetectServicesInput
        ),
        
        StructuredTool.from_function(
            func=enumerate_dns_wrapper,
            name="enumerate_dns",
            description=(
                "DNS reconnaissance: records, subdomains, zone transfers. "
                "Requires dnspython. Comprehensive domain intelligence gathering."
            ),
            args_schema=DNSReconInput
        ),
        
        StructuredTool.from_function(
            func=analyze_ssl_wrapper,
            name="analyze_ssl",
            description=(
                "SSL/TLS certificate analysis and security assessment. "
                "Checks certificate validity, protocols, ciphers, and security issues."
            ),
            args_schema=SSLAnalysisInput
        ),
        
        StructuredTool.from_function(
            func=detect_web_tech_wrapper,
            name="detect_web_technologies",
            description=(
                "Web technology fingerprinting with signature matching. "
                "Detects CMS, frameworks, servers, libraries with confidence scores."
            ),
            args_schema=WebTechDetectionInput
        ),
        
        StructuredTool.from_function(
            func=shodan_lookup_wrapper,
            name="shodan_lookup",
            description=(
                "Shodan passive reconnaissance - lookup IPs or search queries. "
                "Reveals services, vulnerabilities, organization data. Requires API key."
            ),
            args_schema=ShodanLookupInput
        ),
        
        StructuredTool.from_function(
            func=comprehensive_scan_wrapper,
            name="comprehensive_network_scan",
            description=(
                "Full network scan: discovery, ports, services, DNS, SSL, web tech, Shodan. "
                "Modes: quick, standard, full, osint. Comprehensive reconnaissance suite."
            ),
            args_schema=ComprehensiveScanInput
        ),
    ])
    
    return tool_list

if __name__ == "__main__":
    print("Comprehensive Network Scanner - Integrated OSINT Toolkit")
    print("✓ Host discovery (ping, TCP, nmap)")
    print("✓ Port scanning (socket, nmap)")
    print("✓ Service detection with banners")
    print("✓ DNS reconnaissance and enumeration")
    print("✓ SSL/TLS certificate analysis")
    print("✓ Web technology fingerprinting")
    print("✓ Shodan passive reconnaissance")
    print("✓ Full graph memory integration")
    print("✓ Tool chaining compatible")
    print("✓ Modular and extensible")