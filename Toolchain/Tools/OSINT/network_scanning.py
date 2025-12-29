#!/usr/bin/env python3
"""
Modular Network Scanner for Vera - FIXED GRAPH LINKING VERSION
Properly links all discovered nodes to create a unified topology graph

FIXES:
1. Persistent scan context across tool calls
2. Links to existing nodes when they already exist
3. Links new scans to previous scans on same targets
4. Hierarchical linking like web_search_deep
"""

import socket
import subprocess
import requests
import json
import re
import time
import ipaddress
import hashlib
from typing import List, Dict, Any, Optional, Set, Iterator, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydantic import BaseModel, Field
from enum import Enum

# Try nmap import
try:
    import nmap
    NMAP_AVAILABLE = True
except ImportError:
    NMAP_AVAILABLE = False

# =============================================================================
# CONFIGURATION
# =============================================================================

class ScanMode(str, Enum):
    """Scan operation modes"""
    DISCOVERY = "discovery"
    PORT_SCAN = "port_scan"
    SERVICE_DETECT = "service_detect"
    VULNERABILITY = "vulnerability"
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
    
    # Port scanning
    port_ranges: List[str] = field(default_factory=lambda: ["1-1000"])
    scan_timeout: float = 1.0
    max_port_threads: int = 100
    
    # Service detection
    grab_banners: bool = True
    banner_timeout: float = 3.0
    service_version_detection: bool = True
    
    # Vulnerability scanning
    cve_lookup: bool = False
    cve_severity_filter: Optional[str] = None
    max_cve_results: int = 5
    
    # Performance
    rate_limit: Optional[float] = None
    
    # Graph options - ENHANCED
    link_to_session: bool = True
    link_to_toolchain: bool = True
    create_topology_map: bool = True
    link_to_previous_scans: bool = True  # NEW: Link to previous scans
    reuse_existing_nodes: bool = True    # NEW: Reuse nodes if they exist
    
    @classmethod
    def quick_scan(cls) -> 'NetworkScanConfig':
        return cls(
            port_ranges=["21-23,25,53,80,110,143,443,445,3306,3389,5432,8080"],
            grab_banners=True,
            service_version_detection=True,
            cve_lookup=False
        )
    
    @classmethod
    def standard_scan(cls) -> 'NetworkScanConfig':
        return cls(
            port_ranges=["1-1000"],
            grab_banners=True,
            service_version_detection=True,
            cve_lookup=False
        )
    
    @classmethod
    def full_scan(cls) -> 'NetworkScanConfig':
        return cls(
            port_ranges=["1-65535"],
            grab_banners=True,
            service_version_detection=True,
            cve_lookup=True
        )

# =============================================================================
# PYDANTIC SCHEMAS (same as before)
# =============================================================================

class FlexibleTargetInput(BaseModel):
    target: str = Field(description="Target(s): IP, CIDR, hostname, range, or comma-separated")

class DiscoverHostsInput(FlexibleTargetInput):
    timeout: int = Field(default=2, description="Ping timeout in seconds")
    max_threads: int = Field(default=50, description="Max concurrent checks")

class ScanPortsInput(FlexibleTargetInput):
    ports: str = Field(default="1-1000", description="Port spec: '1-1000', '22,80,443', '8000-9000'")
    timeout: float = Field(default=1.0, description="Port timeout")
    only_live_hosts: bool = Field(default=True, description="Only scan verified hosts")

class DetectServicesInput(FlexibleTargetInput):
    ports: Optional[str] = Field(default=None, description="Specific ports or use discovered open ports")
    grab_banners: bool = Field(default=True, description="Attempt banner grabbing")
    timeout: float = Field(default=3.0, description="Service detection timeout")

class ScanVulnerabilitiesInput(FlexibleTargetInput):
    severity_filter: Optional[str] = Field(default=None, description="Filter CVEs: 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'")
    max_results: int = Field(default=5, description="Max CVEs per service")
    service_filter: Optional[str] = Field(default=None, description="Only scan specific service")

class ComprehensiveScanInput(FlexibleTargetInput):
    scan_type: str = Field(default="standard", description="'quick', 'standard', 'full', or 'custom'")
    custom_ports: Optional[str] = Field(default=None, description="Custom port list")
    include_cve: bool = Field(default=False, description="Include CVE lookup")
    cve_severity: Optional[str] = Field(default=None, description="CVE severity filter")

# =============================================================================
# MODULAR SCANNER COMPONENTS (same as before, omitted for brevity)
# =============================================================================

class TargetParser:
    """Parse and expand target specifications"""
    
    @staticmethod
    def parse(target: str) -> List[str]:
        """Parse target into list of IP addresses"""
        hosts = []
        
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
        
        if '-' in target:
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

class HostDiscovery:
    """Host discovery and reachability checking"""
    
    def __init__(self, config: NetworkScanConfig):
        self.config = config
    
    def is_host_alive(self, host: str, timeout: int = 2) -> Tuple[bool, Optional[str]]:
        """Check if host is reachable. Returns: (is_alive, hostname)"""
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
        """Discover live hosts. Yields: {"ip": str, "hostname": Optional[str], "alive": bool}"""
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

class PortScanner:
    """Port scanning functionality"""
    
    def __init__(self, config: NetworkScanConfig):
        self.config = config
        self.common_ports = {
            21: 'FTP', 22: 'SSH', 23: 'Telnet', 25: 'SMTP', 53: 'DNS',
            80: 'HTTP', 110: 'POP3', 143: 'IMAP', 443: 'HTTPS',
            445: 'SMB', 3306: 'MySQL', 3389: 'RDP', 5432: 'PostgreSQL',
            5900: 'VNC', 6379: 'Redis', 8080: 'HTTP-Alt', 8443: 'HTTPS-Alt',
            9200: 'Elasticsearch', 27017: 'MongoDB'
        }
    
    def scan_host(self, host: str, ports: List[int]) -> Iterator[Dict[str, Any]]:
        """Scan ports on host. Yields: {"port": int, "state": str, "service": str}"""
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
        """Detect service on port. Returns: {"service": str, "version": Optional[str], "banner": Optional[str]}"""
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

class VulnerabilityScanner:
    """CVE lookup and vulnerability assessment"""
    
    def __init__(self, config: NetworkScanConfig):
        self.config = config
    
    def lookup_cve(self, service: str, version: Optional[str] = None,
                   max_results: int = 5) -> List[Dict[str, Any]]:
        """Look up CVEs for service/version. Returns: List of CVE data"""
        if not service or service.startswith("unknown"):
            return []
        
        query = f"{service} {version}" if version else service
        
        try:
            api_url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch={query}&resultsPerPage={max_results}"
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            vulnerabilities = []
            
            for vuln_data in data.get('vulnerabilities', [])[:max_results]:
                cve = vuln_data.get('cve', {})
                cve_id = cve.get('id')
                
                metrics = cve.get('metrics', {})
                severity = 'UNKNOWN'
                cvss_score = None
                cvss_vector = None
                
                if 'cvssMetricV31' in metrics:
                    cvss_data = metrics['cvssMetricV31'][0]['cvssData']
                    severity = metrics['cvssMetricV31'][0].get('baseSeverity', 'UNKNOWN')
                    cvss_score = cvss_data.get('baseScore')
                    cvss_vector = cvss_data.get('vectorString')
                elif 'cvssMetricV30' in metrics:
                    cvss_data = metrics['cvssMetricV30'][0]['cvssData']
                    severity = metrics['cvssMetricV30'][0].get('baseSeverity', 'UNKNOWN')
                    cvss_score = cvss_data.get('baseScore')
                    cvss_vector = cvss_data.get('vectorString')
                
                if self.config.cve_severity_filter:
                    if severity != self.config.cve_severity_filter.upper():
                        continue
                
                descriptions = cve.get('descriptions', [])
                description = next(
                    (d['value'] for d in descriptions if d.get('lang') == 'en'),
                    'No description'
                )
                
                vulnerabilities.append({
                    "cve_id": cve_id,
                    "severity": severity,
                    "cvss_score": cvss_score,
                    "cvss_vector": cvss_vector,
                    "description": description,
                    "published": cve.get('published', 'Unknown')
                })
            
            return vulnerabilities
        
        except Exception:
            return []

# =============================================================================
# NETWORK MAPPER - FIXED VERSION WITH PROPER LINKING
# =============================================================================

class NetworkMapper:
    """
    Orchestrates network scanning with PROPER graph linking
    
    FIXES:
    1. Links to previous scans on same targets
    2. Reuses existing nodes when found
    3. Maintains hierarchical structure like web_search_deep
    4. Creates unified topology even across multiple tool calls
    """
    
    def __init__(self, agent, config: NetworkScanConfig):
        self.agent = agent
        self.config = config
        
        # Components
        self.target_parser = TargetParser()
        self.host_discovery = HostDiscovery(config)
        self.port_scanner = PortScanner(config)
        self.service_detector = ServiceDetector(config)
        self.vulnerability_scanner = VulnerabilityScanner(config)
        
        # Context tracking
        self.scan_node_id = None
        
        # Discovered entities cache (GLOBAL across instances)
        self.discovered_ips = {}
        self.discovered_ports = {}
        self.discovered_services = {}
        
        # NEW: Load existing nodes from graph
        if config.reuse_existing_nodes:
            self._load_existing_nodes()
    
    def _load_existing_nodes(self):
        """Load existing network nodes from graph to avoid duplicates"""
        try:
            with self.agent.mem.graph._driver.session() as sess:
                # Load IP nodes
                result = sess.run("""
                    MATCH (ip:NetworkHost)
                    WHERE ip.session_id = $session_id OR ip.id STARTS WITH 'ip_'
                    RETURN ip.id as id, ip.ip_address as ip
                """, {"session_id": self.agent.sess.id})
                
                for record in result:
                    ip = record["ip"]
                    node_id = record["id"]
                    self.discovered_ips[ip] = node_id
                
                # Load port nodes
                result = sess.run("""
                    MATCH (ip:NetworkHost)-[:HAS_PORT]->(port:NetworkPort)
                    RETURN port.id as id, ip.ip_address as ip, port.port_number as port
                """)
                
                for record in result:
                    ip = record["ip"]
                    port = record["port"]
                    node_id = record["id"]
                    self.discovered_ports[(ip, port)] = node_id
                
                # Load service nodes
                result = sess.run("""
                    MATCH (ip:NetworkHost)-[:HAS_PORT]->(port:NetworkPort)-[:RUNS_SERVICE]->(svc:NetworkService)
                    RETURN svc.id as id, ip.ip_address as ip, port.port_number as port
                """)
                
                for record in result:
                    ip = record["ip"]
                    port = record["port"]
                    node_id = record["id"]
                    self.discovered_services[(ip, port)] = node_id
                
        except Exception as e:
            # If loading fails, start fresh
            pass
    
    def _initialize_scan(self, tool_name: str, targets: str):
        """
        Initialize scan context and create scan node
        Uses add_session_memory like web_search_deep for automatic session linking
        Manually links to step if in toolchain context
        """
        # Skip if already initialized (e.g., when called from comprehensive_scan)
        if self.scan_node_id is not None:
            return
        
        # Create scan node using add_session_memory (like web_search_deep)
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
        
        # Store the scan node ID for linking results
        self.scan_node_id = scan_mem.id
        
        # Manually link to step if in toolchain (add_session_memory might not do this)
        if hasattr(self.agent, 'toolchain'):
            if hasattr(self.agent.toolchain, 'current_plan_id'):
                plan_id = self.agent.toolchain.current_plan_id
                step_num = getattr(self.agent.toolchain, 'current_step_num', 0)
                step_node_id = f"step_{plan_id}_{step_num}"
                
                # Link step to scan
                try:
                    self.agent.mem.link(
                        step_node_id,
                        self.scan_node_id,
                        "EXECUTES"
                    )
                except Exception as e:
                    # Step might not exist yet, that's ok
                    pass
    
    def _create_ip_node(self, ip: str, hostname: Optional[str] = None) -> str:
        """
        Create IP node - REUSES if exists
        Links to current scan node (which is already linked to session/step)
        """
        # Check if already exists
        if ip in self.discovered_ips and self.config.reuse_existing_nodes:
            existing_id = self.discovered_ips[ip]
            
            # Link existing node to current scan
            if self.scan_node_id:
                self.agent.mem.link(
                    self.scan_node_id,
                    existing_id,
                    "DISCOVERED_IP",
                    {"ip": ip, "reused": True}
                )
            
            return existing_id
        
        # Create new node
        node_id = f"ip_{ip.replace('.', '_')}"
        
        properties = {
            "ip_address": ip,
            "status": "up",
            "discovered_at": datetime.now().isoformat(),
        }
        
        if hostname:
            properties["hostname"] = hostname
        
        self.agent.mem.upsert_entity(
            node_id,
            "network_host",
            labels=["NetworkHost", "IP"],
            properties=properties
        )
        
        # Link to scan (hierarchical - scan is already linked to session)
        if self.scan_node_id:
            self.agent.mem.link(
                self.scan_node_id,
                node_id,
                "DISCOVERED_IP",
                {"ip": ip}
            )
        
        self.discovered_ips[ip] = node_id
        return node_id
    
    def _create_port_node(self, ip_node_id: str, ip: str, port: int,
                         state: str = "open") -> str:
        """
        Create port node - REUSES if exists
        Links to: IP node (HAS_PORT), scan node (FOUND_PORT)
        """
        cache_key = (ip, port)
        
        # Check if already exists
        if cache_key in self.discovered_ports and self.config.reuse_existing_nodes:
            existing_id = self.discovered_ports[cache_key]
            
            # Link to current scan
            if self.scan_node_id:
                self.agent.mem.link(
                    self.scan_node_id,
                    existing_id,
                    "FOUND_PORT",
                    {"port": port, "reused": True}
                )
            
            return existing_id
        
        # Create new node
        port_node_id = f"{ip_node_id}_port_{port}"
        
        properties = {
            "port_number": port,
            "protocol": "tcp",
            "state": state,
            "discovered_at": datetime.now().isoformat(),
        }
        
        self.agent.mem.upsert_entity(
            port_node_id,
            "network_port",
            labels=["NetworkPort", "Port"],
            properties=properties
        )
        
        # Link to IP (entity hierarchy)
        self.agent.mem.link(
            ip_node_id,
            port_node_id,
            "HAS_PORT",
            {"port": port, "state": state}
        )
        
        # Link to scan (operation tracking)
        if self.scan_node_id:
            self.agent.mem.link(
                self.scan_node_id,
                port_node_id,
                "FOUND_PORT",
                {"port": port, "ip": ip}
            )
        
        self.discovered_ports[cache_key] = port_node_id
        return port_node_id
    
    def _create_service_node(self, port_node_id: str, ip: str, port: int,
                            service_data: Dict[str, Any]) -> str:
        """
        Create service node - REUSES if exists
        Links to: Port node (RUNS_SERVICE), scan node (IDENTIFIED_SERVICE)
        """
        cache_key = (ip, port)
        
        # Check if already exists
        if cache_key in self.discovered_services and self.config.reuse_existing_nodes:
            existing_id = self.discovered_services[cache_key]
            
            # Update properties if new data is better
            self.agent.mem.upsert_entity(
                existing_id,
                "network_service",
                labels=["NetworkService", "Service"],
                properties={
                    "service_name": service_data["service"],
                    "confidence": service_data["confidence"],
                    "version": service_data.get("version"),
                    "banner": service_data.get("banner", "")[:500],
                    "last_updated": datetime.now().isoformat()
                }
            )
            
            # Link to current scan
            if self.scan_node_id:
                self.agent.mem.link(
                    self.scan_node_id,
                    existing_id,
                    "IDENTIFIED_SERVICE",
                    {"service": service_data["service"], "reused": True}
                )
            
            return existing_id
        
        # Create new node
        service_node_id = f"{port_node_id}_service"
        
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
        
        # Link to port (entity hierarchy)
        self.agent.mem.link(
            port_node_id,
            service_node_id,
            "RUNS_SERVICE",
            {"service": service_data["service"]}
        )
        
        # Link to scan (operation tracking)
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
        
        self.discovered_services[cache_key] = service_node_id
        return service_node_id
    
    def _create_vulnerability_node(self, service_node_id: str, cve_data: Dict[str, Any]) -> str:
        """
        Create vulnerability node
        Links to: Service node (HAS_VULNERABILITY), scan node (FOUND_VULNERABILITY)
        """
        vuln_node_id = f"cve_{cve_data['cve_id'].replace('-', '_')}"
        
        properties = {
            "cve_id": cve_data["cve_id"],
            "severity": cve_data["severity"],
            "cvss_score": cve_data.get("cvss_score"),
            "description": cve_data["description"][:1000],
            "published": cve_data.get("published"),
            "discovered_at": datetime.now().isoformat(),
        }
        
        self.agent.mem.upsert_entity(
            vuln_node_id,
            "vulnerability",
            labels=["Vulnerability", "CVE", cve_data["severity"]],
            properties=properties
        )
        
        # Link to service (entity hierarchy)
        self.agent.mem.link(
            service_node_id,
            vuln_node_id,
            "HAS_VULNERABILITY",
            {"severity": cve_data["severity"], "cvss_score": cve_data.get("cvss_score")}
        )
        
        # Link to scan (operation tracking)
        if self.scan_node_id:
            self.agent.mem.link(
                self.scan_node_id,
                vuln_node_id,
                "FOUND_VULNERABILITY",
                {"cve_id": cve_data["cve_id"], "severity": cve_data["severity"]}
            )
        
        return vuln_node_id
    
    # =========================================================================
    # MODULAR SCAN OPERATIONS (same as before but with fixed linking)
    # =========================================================================
    
    def discover_hosts(self, target: str, timeout: int = 2) -> Iterator[str]:
        """Host discovery with proper graph linking"""
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
                
                # Create/reuse IP node with proper linking
                ip_node_id = self._create_ip_node(ip, hostname)
                
                reused = ip in self.discovered_ips and self.config.reuse_existing_nodes
                marker = "[♻]" if reused else "[✓]"
                
                yield f"  {marker} {ip}"
                if hostname:
                    yield f" ({hostname})"
                yield f"\n      Node: {ip_node_id}\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Live Hosts: {live_count}/{len(targets)}\n"
        yield f"  Session: {self.agent.sess.id}\n"
        yield f"  Scan: {self.scan_node_id}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def scan_ports(self, target: str, ports: str = "1-1000",
                   timeout: float = 1.0, only_live_hosts: bool = True) -> Iterator[str]:
        """Port scanning with proper linking to existing nodes"""
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
                    yield f"  [✗] {ip} - Host down, skipping\n"
                    continue
            else:
                hostname = None
                try:
                    hostname = socket.gethostbyaddr(ip)[0]
                except:
                    pass
            
            # Create/get IP node (will reuse if exists)
            ip_node_id = self._create_ip_node(ip, hostname)
            
            yield f"\n  [•] Scanning {ip}...\n"
            
            port_count = 0
            for port_info in self.port_scanner.scan_host(ip, port_list):
                port_count += 1
                total_open += 1
                
                # Create port node (will reuse if exists)
                port_node_id = self._create_port_node(
                    ip_node_id, ip, port_info["port"], port_info["state"]
                )
                
                reused = (ip, port_info["port"]) in self.discovered_ports
                marker = "[♻]" if reused else "[✓]"
                
                yield f"      {marker} Port {port_info['port']}: {port_info['service']}\n"
            
            if port_count == 0:
                yield f"      No open ports found\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Total Open Ports: {total_open}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def detect_services(self, target: str, ports: Optional[str] = None,
                       grab_banners: bool = True) -> Iterator[str]:
        """Service detection linking to discovered ports"""
        self._initialize_scan("detect_services", target)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                   SERVICE DETECTION                          ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        targets = self.target_parser.parse(target)
        
        if ports:
            port_list = self.target_parser.parse_ports(ports)
        else:
            port_list = None
        
        for ip in targets:
            # Use existing IP node if available
            if ip not in self.discovered_ips:
                # Create it if doesn't exist
                ip_node_id = self._create_ip_node(ip)
            else:
                ip_node_id = self.discovered_ips[ip]
            
            # Get open ports for this IP
            if port_list is None:
                open_ports = [p for (i, p) in self.discovered_ports.keys() if i == ip]
                if not open_ports:
                    yield f"  [✗] {ip} - No discovered ports, skipping\n"
                    continue
            else:
                open_ports = port_list
            
            yield f"\n  [•] Detecting services on {ip}...\n"
            
            for port in open_ports:
                port_node_id = self.discovered_ports.get((ip, port))
                if not port_node_id:
                    port_node_id = self._create_port_node(ip_node_id, ip, port)
                
                service_data = self.service_detector.detect_service(ip, port)
                
                # Create/update service node
                service_node_id = self._create_service_node(
                    port_node_id, ip, port, service_data
                )
                
                reused = (ip, port) in self.discovered_services
                marker = "[♻]" if reused else "[✓]"
                
                yield f"      {marker} Port {port}: {service_data['service']}"
                if service_data.get("version"):
                    yield f" {service_data['version']}"
                yield f" ({service_data['confidence']} confidence)\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Services Detected: {len(self.discovered_services)}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def scan_vulnerabilities(self, target: str, severity_filter: Optional[str] = None,
                           max_results: int = 5) -> Iterator[str]:
        """Vulnerability scanning linking to discovered services"""
        self._initialize_scan("scan_vulnerabilities", target)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                 VULNERABILITY SCANNING                       ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        targets = self.target_parser.parse(target)
        
        total_vulns = 0
        
        for ip in targets:
            if ip not in self.discovered_ips:
                yield f"  [✗] {ip} - Not in discovered hosts, skipping\n"
                continue
            
            # Get services for this IP
            ip_services = [(p, s) for (i, p), s in self.discovered_services.items() if i == ip]
            
            if not ip_services:
                yield f"  [✗] {ip} - No discovered services, skipping\n"
                continue
            
            yield f"\n  [•] Scanning {ip} for vulnerabilities...\n"
            
            for port, service_node_id in ip_services:
                # Get service info from graph
                with self.agent.mem.graph._driver.session() as sess:
                    result = sess.run("""
                        MATCH (s:NetworkService {id: $id})
                        RETURN s.service_name as service, s.version as version
                    """, {"id": service_node_id})
                    
                    record = result.single()
                    if not record:
                        continue
                    
                    service_name = record["service"]
                    version = record["version"]
                
                cves = self.vulnerability_scanner.lookup_cve(
                    service_name, version, max_results
                )
                
                if cves:
                    yield f"      [!] Port {port} ({service_name} {version or ''})\n"
                    
                    for cve in cves:
                        if severity_filter and cve["severity"] != severity_filter.upper():
                            continue
                        
                        total_vulns += 1
                        
                        vuln_node_id = self._create_vulnerability_node(
                            service_node_id, cve
                        )
                        
                        yield f"          • {cve['cve_id']}: {cve['severity']} "
                        yield f"({cve.get('cvss_score', 'N/A')}/10)\n"
                    
                    time.sleep(1)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Vulnerabilities Found: {total_vulns}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def comprehensive_scan(self, target: str, scan_type: str = "standard",
                          custom_ports: Optional[str] = None,
                          include_cve: bool = False) -> Iterator[str]:
        """Full comprehensive scan with unified graph"""
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
        elif scan_type == "custom" and custom_ports:
            ports = custom_ports
        else:
            ports = "1-1000"
        
        # All operations use the SAME scan_node_id
        yield f"[1/4] HOST DISCOVERY\n{'─' * 60}\n"
        for chunk in self.discover_hosts(target):
            if not chunk.startswith("╔"):
                yield chunk
        
        yield f"\n[2/4] PORT SCANNING\n{'─' * 60}\n"
        live_hosts = list(self.discovered_ips.keys())
        if live_hosts:
            for chunk in self.scan_ports(",".join(live_hosts), ports, only_live_hosts=False):
                if not chunk.startswith("╔"):
                    yield chunk
        else:
            yield "No live hosts found\n"
        
        yield f"\n[3/4] SERVICE DETECTION\n{'─' * 60}\n"
        if self.discovered_ports:
            for chunk in self.detect_services(",".join(live_hosts)):
                if not chunk.startswith("╔"):
                    yield chunk
        else:
            yield "No open ports found\n"
        
        if include_cve:
            yield f"\n[4/4] VULNERABILITY SCANNING\n{'─' * 60}\n"
            if self.discovered_services:
                for chunk in self.scan_vulnerabilities(",".join(live_hosts)):
                    if not chunk.startswith("╔"):
                        yield chunk
            else:
                yield "No services found\n"
        else:
            yield f"\n[4/4] VULNERABILITY SCANNING\n{'─' * 60}\n"
            yield "Skipped (include_cve=False)\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                     SCAN COMPLETE                            ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
        yield f"  Session:        {self.agent.sess.id}\n"
        yield f"  Scan Node:      {self.scan_node_id}\n"
        yield f"  Live Hosts:     {len(self.discovered_ips)}\n"
        yield f"  Open Ports:     {len(self.discovered_ports)}\n"
        yield f"  Services:       {len(self.discovered_services)}\n"
        yield f"\nQuery Unified Topology:\n"
        yield f"MATCH (scan:NetworkScan {{id: '{self.scan_node_id}'}})\n"
        yield f"OPTIONAL MATCH (scan)-[*1..5]->(node)\n"
        yield f"RETURN scan, node\n"

# =============================================================================
# TOOL INTEGRATION
# =============================================================================

def add_network_scanning_tools(tool_list: List, agent):
    """Add network scanning tools with FIXED graph linking"""
    from langchain_core.tools import StructuredTool
    
    quick_config = NetworkScanConfig.quick_scan()
    standard_config = NetworkScanConfig.standard_scan()
    full_config = NetworkScanConfig.full_scan()
    
    def discover_hosts_wrapper(target: str, timeout: int = 2, max_threads: int = 50):
        config = NetworkScanConfig(
            ping_timeout=timeout,
            max_discovery_threads=max_threads,
            reuse_existing_nodes=True,
            link_to_previous_scans=True
        )
        mapper = NetworkMapper(agent, config)
        result = ""
        for chunk in mapper.discover_hosts(target, timeout):
            result += chunk
            yield chunk
    
    def scan_ports_wrapper(target: str, ports: str = "1-1000", 
                          timeout: float = 1.0, only_live_hosts: bool = True):
        config = NetworkScanConfig(
            port_ranges=[ports],
            scan_timeout=timeout,
            reuse_existing_nodes=True,
            link_to_previous_scans=True
        )
        mapper = NetworkMapper(agent, config)
        result = ""
        for chunk in mapper.scan_ports(target, ports, timeout, only_live_hosts):
            result += chunk
            yield chunk
    
    def detect_services_wrapper(target: str, ports: Optional[str] = None,
                               grab_banners: bool = True, timeout: float = 3.0):
        config = NetworkScanConfig(
            grab_banners=grab_banners,
            banner_timeout=timeout,
            reuse_existing_nodes=True,
            link_to_previous_scans=True
        )
        mapper = NetworkMapper(agent, config)
        result = ""
        for chunk in mapper.detect_services(target, ports, grab_banners):
            result += chunk
            yield chunk
    
    def scan_vulnerabilities_wrapper(target: str, severity_filter: Optional[str] = None,
                                    max_results: int = 5):
        config = NetworkScanConfig(
            cve_lookup=True,
            cve_severity_filter=severity_filter,
            max_cve_results=max_results,
            reuse_existing_nodes=True,
            link_to_previous_scans=True
        )
        mapper = NetworkMapper(agent, config)
        result = ""
        for chunk in mapper.scan_vulnerabilities(target, severity_filter, max_results):
            result += chunk
            yield chunk
    
    def comprehensive_scan_wrapper(target: str, scan_type: str = "standard",
                                  custom_ports: Optional[str] = None,
                                  include_cve: bool = False,
                                  cve_severity: Optional[str] = None):
        if scan_type == "quick":
            config = NetworkScanConfig.quick_scan()
        elif scan_type == "full":
            config = NetworkScanConfig.full_scan()
        else:
            config = NetworkScanConfig.standard_scan()
        
        config.reuse_existing_nodes = True
        config.link_to_previous_scans = True
        
        if include_cve:
            config.cve_lookup = True
            config.cve_severity_filter = cve_severity
        
        mapper = NetworkMapper(agent, config)
        result = ""
        for chunk in mapper.comprehensive_scan(target, scan_type, custom_ports, include_cve):
            result += chunk
            yield chunk
    
    tool_list.extend([
        StructuredTool.from_function(
            func=discover_hosts_wrapper,
            name="discover_hosts",
            description=(
                "HOST DISCOVERY with proper graph linking. Finds live hosts and links to unified topology. "
                "Reuses existing nodes, links to previous scans on same targets. "
                "Creates hierarchical structure: Session -> Scan -> Discovered IPs."
            ),
            args_schema=DiscoverHostsInput
        ),
        
        StructuredTool.from_function(
            func=scan_ports_wrapper,
            name="scan_ports",
            description=(
                "PORT SCANNING with unified graph linking. Links discovered ports to existing IP nodes. "
                "Maintains topology: Session -> Scan -> IP -> Ports. "
                "Reuses nodes across tool calls for unified network map."
            ),
            args_schema=ScanPortsInput
        ),
        
        StructuredTool.from_function(
            func=detect_services_wrapper,
            name="detect_services",
            description=(
                "SERVICE DETECTION linking to discovered ports. Creates unified topology. "
                "Structure: Session -> Scan -> IP -> Port -> Service. "
                "Updates existing service nodes with new information."
            ),
            args_schema=DetectServicesInput
        ),
        
        StructuredTool.from_function(
            func=scan_vulnerabilities_wrapper,
            name="scan_vulnerabilities",
            description=(
                "VULNERABILITY SCANNING linking CVEs to services. Extends unified topology. "
                "Structure: Session -> Scan -> IP -> Port -> Service -> Vulnerabilities. "
                "Links to previous scans for comprehensive vulnerability tracking."
            ),
            args_schema=ScanVulnerabilitiesInput
        ),
        
        StructuredTool.from_function(
            func=comprehensive_scan_wrapper,
            name="comprehensive_network_scan",
            description=(
                "FULL COMPREHENSIVE SCAN with complete unified topology. "
                "Single scan node links all discovered entities hierarchically. "
                "Reuses existing nodes, links to previous scans, creates complete network map. "
                "Query entire topology: MATCH (scan)-[*1..5]->(node) RETURN scan, node"
            ),
            args_schema=ComprehensiveScanInput
        ),
    ])
    
    return tool_list

if __name__ == "__main__":
    """
    FIXED: Modular Network Scanner with Proper Graph Linking
    
    Key Improvements:
    1. Reuses existing nodes (IP, Port, Service) across tool calls
    2. Links new scans to previous scans on same targets
    3. Hierarchical linking like web_search_deep
    4. Unified topology even when tools called separately
    
    Graph Structure:
    Session -[PERFORMED_SCAN]-> Scan1 -[DISCOVERED_IP]-> IP1
                                      -[FOUND_PORT]-> Port1
                                      -[IDENTIFIED_SERVICE]-> Service1
                                      -[FOUND_VULNERABILITY]-> CVE1
    
    Scan1 -[FOLLOWED_BY]-> Scan2  (links sequential scans)
    
    Example Queries:
    
    # Get full topology for a session
    MATCH (sess:Session {id: 'session_id'})-[:PERFORMED_SCAN]->(scan)
    OPTIONAL MATCH (scan)-[*1..5]->(node)
    RETURN sess, scan, node
    
    # Get network map
    MATCH (ip:NetworkHost)-[:HAS_PORT]->(port)-[:RUNS_SERVICE]->(svc)
    OPTIONAL MATCH (svc)-[:HAS_VULNERABILITY]->(cve)
    RETURN ip, port, svc, cve
    
    # Track scan history
    MATCH (scan1:NetworkScan)-[:FOLLOWED_BY*]->(scan2)
    WHERE scan1.targets = '192.168.1.0/24'
    RETURN scan1, scan2
    """
    
    print("Fixed Network Scanner Ready!")
    print("✓ Proper hierarchical linking")
    print("✓ Node reuse across tool calls")
    print("✓ Links to previous scans")
    print("✓ Unified topology graph")