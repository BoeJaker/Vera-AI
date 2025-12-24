#!/usr/bin/env python3
"""
Modular Network Scanner for Vera
Configurable, extensible network reconnaissance with topology mapping

Features:
- Only maps live (reachable) hosts
- Modular scan components (host discovery, port scan, service detection, CVE lookup)
- Composable scan pipelines
- Configuration-driven behavior
- Complete network topology mapping
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
    DISCOVERY = "discovery"           # Host discovery only
    PORT_SCAN = "port_scan"           # Port scanning
    SERVICE_DETECT = "service_detect" # Service detection
    VULNERABILITY = "vulnerability"   # CVE lookup
    FULL = "full"                     # Complete scan

@dataclass
class NetworkScanConfig:
    """Configuration for network scanning operations"""
    
    # Target specification
    targets: List[str] = field(default_factory=list)
    
    # Host discovery
    ping_timeout: int = 2
    verify_hosts: bool = True  # Only create nodes for reachable hosts
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
    rate_limit: Optional[float] = None  # Delay between operations
    
    # Graph options
    link_to_session: bool = True
    link_to_toolchain: bool = True
    create_topology_map: bool = True
    
    @classmethod
    def quick_scan(cls) -> 'NetworkScanConfig':
        """Quick scan: common ports, no CVE lookup"""
        return cls(
            port_ranges=["21-23,25,53,80,110,143,443,445,3306,3389,5432,8080"],
            grab_banners=True,
            service_version_detection=True,
            cve_lookup=False
        )
    
    @classmethod
    def standard_scan(cls) -> 'NetworkScanConfig':
        """Standard scan: top 1000 ports, service detection"""
        return cls(
            port_ranges=["1-1000"],
            grab_banners=True,
            service_version_detection=True,
            cve_lookup=False
        )
    
    @classmethod
    def full_scan(cls) -> 'NetworkScanConfig':
        """Full scan: all ports, services, CVE lookup"""
        return cls(
            port_ranges=["1-65535"],
            grab_banners=True,
            service_version_detection=True,
            cve_lookup=True
        )
    
    @classmethod
    def vulnerability_only(cls) -> 'NetworkScanConfig':
        """Vulnerability scan only (assumes hosts/services already discovered)"""
        return cls(
            verify_hosts=False,  # Don't re-verify
            port_ranges=[],      # Don't scan ports
            grab_banners=False,
            cve_lookup=True
        )

# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class FlexibleTargetInput(BaseModel):
    target: str = Field(
        description="Target(s): IP, CIDR, hostname, range, or comma-separated"
    )

class DiscoverHostsInput(FlexibleTargetInput):
    timeout: int = Field(default=2, description="Ping timeout in seconds")
    max_threads: int = Field(default=50, description="Max concurrent checks")

class ScanPortsInput(FlexibleTargetInput):
    ports: str = Field(
        default="1-1000",
        description="Port spec: '1-1000', '22,80,443', '8000-9000'"
    )
    timeout: float = Field(default=1.0, description="Port timeout")
    only_live_hosts: bool = Field(default=True, description="Only scan verified hosts")

class DetectServicesInput(FlexibleTargetInput):
    ports: Optional[str] = Field(
        default=None,
        description="Specific ports or use discovered open ports"
    )
    grab_banners: bool = Field(default=True, description="Attempt banner grabbing")
    timeout: float = Field(default=3.0, description="Service detection timeout")

class ScanVulnerabilitiesInput(FlexibleTargetInput):
    severity_filter: Optional[str] = Field(
        default=None,
        description="Filter CVEs: 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'"
    )
    max_results: int = Field(default=5, description="Max CVEs per service")
    service_filter: Optional[str] = Field(
        default=None,
        description="Only scan specific service (e.g., 'SSH', 'HTTP')"
    )

class ComprehensiveScanInput(FlexibleTargetInput):
    scan_type: str = Field(
        default="standard",
        description="'quick', 'standard', 'full', or 'custom'"
    )
    custom_ports: Optional[str] = Field(default=None, description="Custom port list")
    include_cve: bool = Field(default=False, description="Include CVE lookup")
    cve_severity: Optional[str] = Field(default=None, description="CVE severity filter")

# =============================================================================
# MODULAR SCANNER COMPONENTS
# =============================================================================

class TargetParser:
    """Parse and expand target specifications"""
    
    @staticmethod
    def parse(target: str) -> List[str]:
        """Parse target into list of IP addresses"""
        hosts = []
        
        # Comma-separated
        if ',' in target:
            for t in target.split(','):
                hosts.extend(TargetParser.parse(t.strip()))
            return list(set(hosts))
        
        # CIDR notation
        if '/' in target:
            try:
                network = ipaddress.ip_network(target, strict=False)
                return [str(ip) for ip in network.hosts()]
            except ValueError:
                pass
        
        # IP range
        if '-' in target:
            try:
                # Full range: 192.168.1.1-192.168.1.10
                if target.count('.') >= 6:
                    start_ip, end_ip = target.split('-')
                    start = ipaddress.IPv4Address(start_ip.strip())
                    end = ipaddress.IPv4Address(end_ip.strip())
                    return [str(ipaddress.IPv4Address(ip)) 
                            for ip in range(int(start), int(end) + 1)]
                
                # Abbreviated: 192.168.1.1-10
                else:
                    base, range_part = target.rsplit('.', 1)
                    if '-' in range_part:
                        start, end = map(int, range_part.split('-'))
                        return [f"{base}.{i}" for i in range(start, end + 1)]
            except (ValueError, ipaddress.AddressValueError):
                pass
        
        # Single IP or hostname
        try:
            ipaddress.ip_address(target)
            hosts.append(target)
        except ValueError:
            # Try hostname resolution
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
        """
        Check if host is reachable
        Returns: (is_alive, hostname)
        """
        # Try ICMP ping
        try:
            result = subprocess.run(
                ['ping', '-c', '1', '-W', str(timeout), host],
                capture_output=True,
                timeout=timeout + 1
            )
            if result.returncode == 0:
                # Try to get hostname
                hostname = None
                try:
                    hostname = socket.gethostbyaddr(host)[0]
                except socket.herror:
                    pass
                return True, hostname
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # Fallback: TCP connection to common ports
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
        """Quick TCP port check"""
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
        """
        Discover live hosts from target list
        Yields: {"ip": str, "hostname": Optional[str], "alive": bool}
        """
        def check_host(ip):
            alive, hostname = self.is_host_alive(ip, self.config.ping_timeout)
            return {"ip": ip, "hostname": hostname, "alive": alive}
        
        with ThreadPoolExecutor(max_workers=self.config.max_discovery_threads) as executor:
            futures = {executor.submit(check_host, ip): ip for ip in targets}
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result["alive"]:  # Only yield live hosts
                        yield result
                except Exception as e:
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
        """
        Scan ports on a single host
        Yields: {"port": int, "state": str, "service": str}
        """
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
        """
        Detect service on specific port
        Returns: {"service": str, "version": Optional[str], "banner": Optional[str]}
        """
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
        
        # Detect service from banner
        service, version = self._identify_service(banner, port)
        if service:
            result["service"] = service
            result["version"] = version
            result["confidence"] = "high" if version else "medium"
        
        return result
    
    def _grab_banner(self, host: str, port: int) -> Optional[str]:
        """Grab service banner"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.config.banner_timeout)
        
        try:
            sock.connect((host, port))
            
            # Send HTTP request for HTTP ports
            if port in [80, 8080, 8000, 8888, 5000]:
                sock.send(b"GET / HTTP/1.0\r\nHost: " + host.encode() + b"\r\n\r\n")
            
            banner = sock.recv(4096)
            return banner.decode('utf-8', errors='ignore').strip()
        
        except socket.error:
            return None
        finally:
            sock.close()
    
    def _identify_service(self, banner: str, port: int) -> Tuple[Optional[str], Optional[str]]:
        """Identify service and version from banner"""
        banner_lower = banner.lower()
        
        # Check signatures
        for service, signatures in self.service_signatures.items():
            if any(sig.decode('utf-8', errors='ignore').lower() in banner_lower 
                   for sig in signatures):
                version = self._extract_version(banner)
                return service, version
        
        # Fallback to port-based guess
        return None, None
    
    def _extract_version(self, banner: str) -> Optional[str]:
        """Extract version from banner"""
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
        """
        Look up CVEs for service/version
        Returns: List of CVE data
        """
        if not service or service.startswith("unknown"):
            return []
        
        # Build search query
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
                
                # Get severity
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
                
                # Filter by severity if specified
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
        
        except Exception as e:
            return []


# =============================================================================
# NETWORK MAPPER - ORCHESTRATES SCANNING & BUILDS TOPOLOGY
# =============================================================================

class NetworkMapper:
    """
    Orchestrates network scanning and builds topology graph
    Only creates nodes for live/reachable entities
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
        self.step_node_id = None
        
        # Discovered entities cache
        self.discovered_ips = {}      # ip -> node_id
        self.discovered_ports = {}    # (ip, port) -> node_id
        self.discovered_services = {} # (ip, port) -> node_id
    
    def _initialize_scan(self, tool_name: str, targets: str):
        """Initialize scan context and create scan node"""
        scan_id = f"scan_{int(time.time()*1000)}_{hashlib.md5(targets.encode()).hexdigest()[:8]}"
        self.scan_node_id = scan_id
        
        properties = {
            "tool": tool_name,
            "targets": targets,
            "started_at": datetime.now().isoformat(),
            "session_id": self.agent.sess.id,
        }
        
        # Detect toolchain context
        context = self._detect_toolchain_context()
        if context:
            plan_id, step_num = context
            properties["plan_id"] = plan_id
            properties["step_num"] = step_num
            self.step_node_id = f"step_{plan_id}_{step_num}"
        
        # Create scan node
        self.agent.mem.upsert_entity(
            scan_id,
            "network_scan",
            labels=["NetworkScan", "Scan"],
            properties=properties
        )
        
        # Link to session
        self.agent.mem.graph.link_session_to_entity(
            self.agent.sess.id,
            scan_id,
            "PERFORMED_SCAN"
        )
        
        # Link to step if in toolchain
        if self.step_node_id:
            self.agent.mem.link(
                self.step_node_id,
                scan_id,
                "EXECUTES_SCAN"
            )
    
    def _detect_toolchain_context(self) -> Optional[Tuple[str, int]]:
        """Detect if running in toolchain"""
        if hasattr(self.agent, 'toolchain'):
            if hasattr(self.agent.toolchain, 'current_plan_id'):
                plan_id = self.agent.toolchain.current_plan_id
                step_num = getattr(self.agent.toolchain, 'current_step_num', 0)
                return (plan_id, step_num)
        return None
    
    def _link_to_context(self, node_id: str, rel_type: str, metadata: Optional[Dict] = None):
        """Link node to session, scan, and step"""
        metadata = metadata or {}
        
        # Link to session
        self.agent.mem.graph.link_session_to_entity(
            self.agent.sess.id,
            node_id,
            rel_type
        )
        
        # Link to scan
        if self.scan_node_id:
            self.agent.mem.link(
                self.scan_node_id,
                node_id,
                rel_type,
                metadata
            )
        
        # Link to step
        if self.step_node_id:
            self.agent.mem.link(
                self.step_node_id,
                node_id,
                rel_type,
                metadata
            )
    
    def _create_ip_node(self, ip: str, hostname: Optional[str] = None) -> str:
        """Create IP node (only if not already exists)"""
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
        
        self.agent.mem.upsert_entity(
            node_id,
            "network_host",
            labels=["NetworkHost", "IP"],
            properties=properties
        )
        
        self._link_to_context(node_id, "DISCOVERED_IP", {"ip": ip})
        
        self.discovered_ips[ip] = node_id
        return node_id
    
    def _create_port_node(self, ip_node_id: str, ip: str, port: int, 
                         state: str = "open") -> str:
        """Create port node"""
        cache_key = (ip, port)
        if cache_key in self.discovered_ports:
            return self.discovered_ports[cache_key]
        
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
        
        # Link port to IP
        self.agent.mem.link(
            ip_node_id,
            port_node_id,
            "HAS_PORT",
            {"port": port}
        )
        
        self._link_to_context(port_node_id, "FOUND_PORT", {"port": port})
        
        self.discovered_ports[cache_key] = port_node_id
        return port_node_id
    
    def _create_service_node(self, port_node_id: str, ip: str, port: int,
                            service_data: Dict[str, Any]) -> str:
        """Create service node"""
        cache_key = (ip, port)
        if cache_key in self.discovered_services:
            return self.discovered_services[cache_key]
        
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
        
        # Link service to port
        self.agent.mem.link(
            port_node_id,
            service_node_id,
            "RUNS_SERVICE",
            {"service": service_data["service"]}
        )
        
        self._link_to_context(
            service_node_id,
            "IDENTIFIED_SERVICE",
            {"service": service_data["service"], "version": service_data.get("version")}
        )
        
        self.discovered_services[cache_key] = service_node_id
        return service_node_id
    
    def _create_vulnerability_node(self, service_node_id: str, cve_data: Dict[str, Any]) -> str:
        """Create vulnerability node"""
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
        
        # Link to service
        self.agent.mem.link(
            service_node_id,
            vuln_node_id,
            "HAS_VULNERABILITY",
            {"severity": cve_data["severity"], "cvss_score": cve_data.get("cvss_score")}
        )
        
        self._link_to_context(
            vuln_node_id,
            "FOUND_VULNERABILITY",
            {"cve_id": cve_data["cve_id"], "severity": cve_data["severity"]}
        )
        
        return vuln_node_id
    
    # =========================================================================
    # MODULAR SCAN OPERATIONS
    # =========================================================================
    
    def discover_hosts(self, target: str, timeout: int = 2) -> Iterator[str]:
        """
        Host discovery only - finds live hosts
        ONLY creates IP nodes for reachable hosts
        """
        self._initialize_scan("discover_hosts", target)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                     HOST DISCOVERY                           ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        # Parse targets
        targets = self.target_parser.parse(target)
        yield f"Checking {len(targets)} target(s)...\n\n"
        
        live_count = 0
        
        for host_info in self.host_discovery.discover_live_hosts(targets):
            if host_info["alive"]:
                live_count += 1
                ip = host_info["ip"]
                hostname = host_info["hostname"]
                
                # Create IP node
                ip_node_id = self._create_ip_node(ip, hostname)
                
                yield f"  [✓] {ip}"
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
        """
        Port scanning only
        Can use previously discovered hosts or scan new targets
        """
        self._initialize_scan("scan_ports", target)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                      PORT SCANNING                           ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        # Parse targets and ports
        targets = self.target_parser.parse(target)
        port_list = self.target_parser.parse_ports(ports)
        
        yield f"Targets: {len(targets)}\n"
        yield f"Ports: {len(port_list)}\n\n"
        
        total_open = 0
        
        for ip in targets:
            # Check if host is live (or skip check if not required)
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
            
            # Create/get IP node
            ip_node_id = self._create_ip_node(ip, hostname)
            
            yield f"\n  [•] Scanning {ip}...\n"
            
            port_count = 0
            for port_info in self.port_scanner.scan_host(ip, port_list):
                port_count += 1
                total_open += 1
                
                # Create port node
                port_node_id = self._create_port_node(
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
        """
        Service detection only
        Uses discovered open ports or specified ports
        """
        self._initialize_scan("detect_services", target)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                   SERVICE DETECTION                          ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        targets = self.target_parser.parse(target)
        
        # If ports specified, use those; otherwise use discovered ports
        if ports:
            port_list = self.target_parser.parse_ports(ports)
        else:
            port_list = None
        
        for ip in targets:
            # Get IP node (must exist from previous scan)
            if ip not in self.discovered_ips:
                yield f"  [✗] {ip} - Not in discovered hosts, skipping\n"
                continue
            
            ip_node_id = self.discovered_ips[ip]
            
            # Get open ports for this IP
            if port_list is None:
                # Use discovered ports
                open_ports = [p for (i, p) in self.discovered_ports.keys() if i == ip]
                if not open_ports:
                    yield f"  [✗] {ip} - No discovered ports, skipping\n"
                    continue
            else:
                # Use specified ports
                open_ports = port_list
            
            yield f"\n  [•] Detecting services on {ip}...\n"
            
            for port in open_ports:
                port_node_id = self.discovered_ports.get((ip, port))
                if not port_node_id:
                    # Create port node if it doesn't exist
                    port_node_id = self._create_port_node(ip_node_id, ip, port)
                
                # Detect service
                service_data = self.service_detector.detect_service(ip, port)
                
                # Create service node
                service_node_id = self._create_service_node(
                    port_node_id, ip, port, service_data
                )
                
                yield f"      [✓] Port {port}: {service_data['service']}"
                if service_data.get("version"):
                    yield f" {service_data['version']}"
                yield f" ({service_data['confidence']} confidence)\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Services Detected: {len(self.discovered_services)}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def scan_vulnerabilities(self, target: str, severity_filter: Optional[str] = None,
                           max_results: int = 5) -> Iterator[str]:
        """
        Vulnerability scanning only
        Uses discovered services to look up CVEs
        """
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
                
                # Look up CVEs
                cves = self.vulnerability_scanner.lookup_cve(
                    service_name, version, max_results
                )
                
                if cves:
                    yield f"      [!] Port {port} ({service_name} {version or ''})\n"
                    
                    for cve in cves:
                        if severity_filter and cve["severity"] != severity_filter.upper():
                            continue
                        
                        total_vulns += 1
                        
                        # Create vulnerability node
                        vuln_node_id = self._create_vulnerability_node(
                            service_node_id, cve
                        )
                        
                        yield f"          • {cve['cve_id']}: {cve['severity']} "
                        yield f"({cve.get('cvss_score', 'N/A')}/10)\n"
                    
                    time.sleep(1)  # Rate limiting
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Vulnerabilities Found: {total_vulns}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def comprehensive_scan(self, target: str, scan_type: str = "standard",
                          custom_ports: Optional[str] = None,
                          include_cve: bool = False) -> Iterator[str]:
        """
        Full comprehensive scan - all operations in sequence
        Only creates nodes for live/reachable entities
        """
        self._initialize_scan("comprehensive_scan", target)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║              COMPREHENSIVE NETWORK SCAN                      ║\n"
        yield f"║                  Mode: {scan_type.upper():^30}              ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        # Configure based on scan type
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
        
        # Step 1: Host Discovery
        yield f"[1/4] HOST DISCOVERY\n"
        yield f"{'─' * 60}\n"
        for chunk in self.discover_hosts(target):
            if not chunk.startswith("╔"):  # Skip headers from nested calls
                yield chunk
        
        # Step 2: Port Scanning
        yield f"\n[2/4] PORT SCANNING\n"
        yield f"{'─' * 60}\n"
        live_hosts = list(self.discovered_ips.keys())
        if live_hosts:
            for chunk in self.scan_ports(",".join(live_hosts), ports, only_live_hosts=False):
                if not chunk.startswith("╔"):
                    yield chunk
        else:
            yield "No live hosts found\n"
        
        # Step 3: Service Detection
        yield f"\n[3/4] SERVICE DETECTION\n"
        yield f"{'─' * 60}\n"
        if self.discovered_ports:
            for chunk in self.detect_services(",".join(live_hosts)):
                if not chunk.startswith("╔"):
                    yield chunk
        else:
            yield "No open ports found\n"
        
        # Step 4: Vulnerability Scanning (optional)
        if include_cve:
            yield f"\n[4/4] VULNERABILITY SCANNING\n"
            yield f"{'─' * 60}\n"
            if self.discovered_services:
                for chunk in self.scan_vulnerabilities(",".join(live_hosts)):
                    if not chunk.startswith("╔"):
                        yield chunk
            else:
                yield "No services found\n"
        else:
            yield f"\n[4/4] VULNERABILITY SCANNING\n"
            yield f"{'─' * 60}\n"
            yield "Skipped (include_cve=False)\n"
        
        # Final Summary
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                     SCAN COMPLETE                            ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
        yield f"  Session:        {self.agent.sess.id}\n"
        yield f"  Scan Node:      {self.scan_node_id}\n"
        yield f"  Live Hosts:     {len(self.discovered_ips)}\n"
        yield f"  Open Ports:     {len(self.discovered_ports)}\n"
        yield f"  Services:       {len(self.discovered_services)}\n"
        yield f"\nQuery Network Topology:\n"
        yield f"MATCH (s:Session {{id: '{self.agent.sess.id}'}})-[:DISCOVERED_IP]->(ip:NetworkHost)\n"
        yield f"OPTIONAL MATCH (ip)-[:HAS_PORT]->(port)-[:RUNS_SERVICE]->(svc)\n"
        yield f"RETURN ip, port, svc\n"


# =============================================================================
# TOOL INTEGRATION
# =============================================================================

def add_network_scanning_tools(tool_list: List, agent):
    """
    Add modular network scanning tools
    Each tool is focused and composable
    """
    from langchain_core.tools import StructuredTool
    
    # Quick scan config
    quick_config = NetworkScanConfig.quick_scan()
    standard_config = NetworkScanConfig.standard_scan()
    full_config = NetworkScanConfig.full_scan()
    
    # Discover Hosts Tool
    def discover_hosts_wrapper(target: str, timeout: int = 2, max_threads: int = 50):
        config = NetworkScanConfig(
            ping_timeout=timeout,
            max_discovery_threads=max_threads
        )
        mapper = NetworkMapper(agent, config)
        result = ""
        for chunk in mapper.discover_hosts(target, timeout):
            result += chunk
            yield chunk
    
    # Port Scan Tool
    def scan_ports_wrapper(target: str, ports: str = "1-1000", 
                          timeout: float = 1.0, only_live_hosts: bool = True):
        config = NetworkScanConfig(
            port_ranges=[ports],
            scan_timeout=timeout
        )
        mapper = NetworkMapper(agent, config)
        result = ""
        for chunk in mapper.scan_ports(target, ports, timeout, only_live_hosts):
            result += chunk
            yield chunk
    
    # Service Detection Tool
    def detect_services_wrapper(target: str, ports: Optional[str] = None,
                               grab_banners: bool = True, timeout: float = 3.0):
        config = NetworkScanConfig(
            grab_banners=grab_banners,
            banner_timeout=timeout
        )
        mapper = NetworkMapper(agent, config)
        result = ""
        for chunk in mapper.detect_services(target, ports, grab_banners):
            result += chunk
            yield chunk
    
    # Vulnerability Scan Tool
    def scan_vulnerabilities_wrapper(target: str, severity_filter: Optional[str] = None,
                                    max_results: int = 5):
        config = NetworkScanConfig(
            cve_lookup=True,
            cve_severity_filter=severity_filter,
            max_cve_results=max_results
        )
        mapper = NetworkMapper(agent, config)
        result = ""
        for chunk in mapper.scan_vulnerabilities(target, severity_filter, max_results):
            result += chunk
            yield chunk
    
    # Comprehensive Scan Tool
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
                "HOST DISCOVERY ONLY. Find live hosts from targets (IP/CIDR/range/hostname). "
                "ONLY creates nodes for reachable hosts. Fast parallel checking. "
                "Use when you only need to know which hosts are up."
            ),
            args_schema=DiscoverHostsInput
        ),
        
        StructuredTool.from_function(
            func=scan_ports_wrapper,
            name="scan_ports",
            description=(
                "PORT SCANNING ONLY. Scan ports on target hosts. "
                "Can use previously discovered hosts or scan new targets. "
                "Creates port nodes for open ports only. Fast multi-threaded scanning. "
                "Use when you need to find open ports on known hosts."
            ),
            args_schema=ScanPortsInput
        ),
        
        StructuredTool.from_function(
            func=detect_services_wrapper,
            name="detect_services",
            description=(
                "SERVICE DETECTION ONLY. Identify services on discovered ports. "
                "Grabs banners, detects versions, identifies service types. "
                "Creates service nodes with version info. "
                "Use after port scanning to identify what's running."
            ),
            args_schema=DetectServicesInput
        ),
        
        StructuredTool.from_function(
            func=scan_vulnerabilities_wrapper,
            name="scan_vulnerabilities",
            description=(
                "VULNERABILITY SCANNING ONLY. Look up CVEs for discovered services. "
                "Queries NVD database, filters by severity, creates CVE nodes. "
                "Use after service detection to find known vulnerabilities. "
                "Rate-limited to avoid API throttling."
            ),
            args_schema=ScanVulnerabilitiesInput
        ),
        
        StructuredTool.from_function(
            func=comprehensive_scan_wrapper,
            name="comprehensive_network_scan",
            description=(
                "FULL COMPREHENSIVE SCAN. Runs all scan phases in sequence: "
                "1) Host discovery, 2) Port scanning, 3) Service detection, 4) CVE lookup. "
                "ONLY creates nodes for live/reachable entities. "
                "Modes: 'quick' (common ports), 'standard' (1-1000), 'full' (all ports). "
                "Creates complete network topology map. Use for thorough network assessment."
            ),
            args_schema=ComprehensiveScanInput
        ),
    ])
    
    return tool_list


if __name__ == "__main__":
    """
    Modular Network Scanner
    
    Features:
    - Only maps live hosts (no dead IPs in graph)
    - Composable scan operations
    - Configuration-driven
    - Complete topology mapping
    
    Usage Examples:
    
    # Discovery only
    "discover live hosts on 192.168.1.0/24"
    
    # Port scan only
    "scan ports 1-1000 on 192.168.1.100"
    
    # Service detection only
    "detect services on 192.168.1.100"
    
    # Vulnerability scan only
    "scan for critical CVEs on 192.168.1.100"
    
    # Full comprehensive scan
    "comprehensive scan 192.168.1.0/24 with CVE lookup"
    
    # Custom workflow
    "discover hosts on 10.0.0.0/24, then scan common ports, detect services, find high severity CVEs"
    """
    
    print("Modular Network Scanner Ready!")
    print("- Only maps live hosts")
    print("- Composable operations")
    print("- Configurable scans")
    print("- Complete topology mapping")