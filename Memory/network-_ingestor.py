#!/usr/bin/env python3
"""
Network Infrastructure Ingestor for Hybrid Memory System
Ingests networks, websites, infrastructure, cloud resources, and topology
into a graph-based memory system with semantic relationships.

Dependencies:
    pip install scapy nmap dnspython requests beautifulsoup4 selenium
    pip install boto3 azure-mgmt-network google-cloud-compute kubernetes
    pip install docker paramiko netmiko pysnmp
    pip install whois python-whois ipwhois
    pip install networkx matplotlib

Features:
- Physical/Virtual network topology mapping
- Cloud infrastructure discovery (AWS, Azure, GCP, Kubernetes)
- Website structure and asset discovery
- Active/passive network scanning
- Service detection and fingerprinting
- DNS/WHOIS enrichment
- Configuration management database (CMDB) integration
- Real-time network monitoring integration
"""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import re
import socket
import ssl
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import dns.resolver
import requests
from bs4 import BeautifulSoup

# Network scanning
try:
    import nmap
    NMAP_AVAILABLE = True
except ImportError:
    NMAP_AVAILABLE = False

try:
    from scapy.all import ARP, Ether, srp, IP, ICMP, sr1, TCP
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False

# Cloud providers
try:
    import boto3
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False

try:
    from azure.identity import DefaultAzureCredential
    from azure.mgmt.network import NetworkManagementClient
    from azure.mgmt.compute import ComputeManagementClient
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

try:
    from google.cloud import compute_v1
    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False

try:
    from kubernetes import client, config
    K8S_AVAILABLE = True
except ImportError:
    K8S_AVAILABLE = False

try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

# Import your memory system
import sys
from pathlib import Path

# Add parent directory to sys.path for relative imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from memory import HybridMemory, Node, Edge


# ==================== Data Models ====================

@dataclass
class NetworkNode:
    """Represents a network node (host, router, switch, etc.)"""
    name: str
    ip: str
    hostname: Optional[str] = None
    mac: Optional[str] = None
    node_type: str = "host"  # host, router, switch, firewall, loadbalancer
    os: Optional[str] = None
    vendor: Optional[str] = None
    services: List[Dict[str, Any]] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.services is None:
            self.services = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class NetworkLink:
    """Represents a network connection between nodes"""
    source: str
    target: str
    link_type: str  # physical, virtual, vpn, tunnel, route
    protocol: Optional[str] = None
    port: Optional[int] = None
    bandwidth: Optional[str] = None
    latency: Optional[float] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class NetworkSegment:
    """Represents a network segment/subnet"""
    name: str
    cidr: str
    vlan: Optional[int] = None
    segment_type: str = "lan"  # lan, wan, dmz, internal, external
    gateway: Optional[str] = None
    dns_servers: List[str] = None
    dhcp_range: Optional[Tuple[str, str]] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.dns_servers is None:
            self.dns_servers = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class WebAsset:
    """Represents a web asset (page, API endpoint, resource)"""
    name: str
    id: str
    url: str
    asset_type: str  # page, api, image, script, stylesheet, document
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    size: Optional[int] = None
    headers: Dict[str, str] = None
    technologies: List[str] = None
    security_headers: Dict[str, Any] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.technologies is None:
            self.technologies = []
        if self.security_headers is None:
            self.security_headers = {}
        if self.metadata is None:
            self.metadata = {}


@dataclass
class CloudResource:
    """Represents a cloud infrastructure resource"""
    name: str
    resource_id: str
    resource_type: str  # vm, container, function, database, storage, network
    provider: str  # aws, azure, gcp, kubernetes
    region: Optional[str] = None
    zone: Optional[str] = None
    state: Optional[str] = None
    tags: Dict[str, str] = None
    configuration: Dict[str, Any] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}
        if self.configuration is None:
            self.configuration = {}
        if self.metadata is None:
            self.metadata = {}


try:
    import nmap
    NMAP_AVAILABLE = True
except ImportError:
    NMAP_AVAILABLE = False

try:
    import netifaces
except ImportError:
    netifaces = None

class NetworkNode:
    def __init__(self, ip: str, hostname: str = None, node_type: str = "host"):
        self.name = ip
        self.ip = ip
        self.hostname = hostname
        self.node_type = node_type
        self.services = []

class NetworkSegment:
    def __init__(self, cidr: str, name: str, segment_type: str = "lan", gateway: Optional[str] = None):
        self.cidr = cidr
        self.name = name
        self.segment_type = segment_type
        self.gateway = gateway

class NetworkScanner:
    def __init__(self):
        self.discovered_hosts = {}
        self.discovered_segments = {}

    async def discover_local_network(self, ingestor, interface: Optional[str] = None, timeout: int = 3) -> Dict[str, Any]:
        """
        Discover devices on the local network using ping/TCP scan.
        Works without root/admin privileges.
        """
        results = {"network": None, "hosts": [], "segments": []}

        try:
            if netifaces is None:
                raise RuntimeError("netifaces is required for local network discovery")

            # Determine interface
            if interface is None:
                gw = netifaces.gateways()['default'][netifaces.AF_INET]
                interface = gw[1]

            addrs = netifaces.ifaddresses(interface)
            ip = addrs[netifaces.AF_INET][0]['addr']
            netmask = addrs[netifaces.AF_INET][0]['netmask']

            # Calculate network CIDR
            network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
            results["network"] = str(network)

            # Scan network for hosts
            hosts = []

            if NMAP_AVAILABLE:
                nm = nmap.PortScanner()
                nm.scan(hosts=str(network), arguments='-sn')  # ping scan
                for host_ip in nm.all_hosts():
                    if nm[host_ip].state() == "up":
                        try:
                            hostname = nm[host_ip].hostname() or None
                        except:
                            hostname = None
                        node = NetworkNode(host_ip, hostname)
                        print(node.__dict__)
                        hosts.append(node)
                        self.discovered_hosts[host_ip] = node
            else:
                # Fallback: TCP connect to port 80
                async def try_connect(ip_addr: str):
                    try:
                        fut = asyncio.open_connection(ip_addr, 80)
                        reader, writer = await asyncio.wait_for(fut, timeout=timeout)
                        writer.close()
                        await writer.wait_closed()
                        try:
                            hostname = socket.gethostbyaddr(ip_addr)[0]
                        except:
                            hostname = None
                        node = NetworkNode(ip_addr, hostname)
                        self.discovered_hosts[ip_addr] = node
                        print(vars(node))
                        return node
                    except Exception as e:
                        # print(f"Host {ip_addr} is down or unreachable:\n{e}")
                        return None
                try:
                    tasks = [try_connect(str(ip)) for ip in network.hosts()]
                    results_list = await asyncio.gather(*tasks)
                    hosts = [h for h in results_list if h]
                except Exception as e:
                    print(f"Error during TCP connect scan:\n {e}")

            results["hosts"] = hosts

            # Create a network segment
            gateway_ip = str(network.network_address + 1)
            segment = NetworkSegment(
                cidr=str(network),
                name=f"Local Network {interface}",
                segment_type="lan",
                gateway=gateway_ip
            )
            ingestor.discovered_segments[str(network)] = segment
            results["segments"].append(segment)

            for host in results["hosts"]:
                ingestor.discovered_hosts[host.ip] = host
                await ingestor._ingest_network_node(host)

        except Exception as e:
            print(f"Error during local network discovery: {e}")
            results["error"] = str(e)

        return results

# ==================== Network Infrastructure Ingestor ====================

class NetworkInfrastructureIngestor:
    """
    Comprehensive network and infrastructure discovery and ingestion.
    """
    
    def __init__(self, memory: Any, credentials: Optional[Dict[str, Any]] = None):
        """
        Args:
            memory: HybridMemory instance
            credentials: Dict with cloud provider credentials and API keys
        """
        self.memory = memory
        self.credentials = credentials or {}
        
        # Tracking
        self.discovered_hosts: Dict[str, NetworkNode] = {}
        self.discovered_links: List[NetworkLink] = []
        self.discovered_segments: Dict[str, NetworkSegment] = {}
        self.discovered_websites: Dict[str, Dict[str, Any]] = {}
        self.discovered_web_assets: Dict[str, WebAsset] = {}
        self.discovered_services: Dict[str, Dict[str, Any]] = {}
        self.discovered_cloud_resources: Dict[str, CloudResource] = {}

        # Caches
        self.dns_cache: Dict[str, str] = {}
        self.whois_cache: Dict[str, Dict[str, Any]] = {}
        
    # ==================== Physical/Virtual Network Discovery ====================
    
    async def scan_network_range(self, cidr: str, scan_type: str = "ping") -> Dict[str, Any]:
        """
        Scan a network range for active hosts.
        
        Args:
            cidr: CIDR notation (e.g., 192.168.1.0/24)
            scan_type: ping, syn, comprehensive
        """
        results = {
            "cidr": cidr,
            "scan_type": scan_type,
            "hosts": [],
            "total_scanned": 0,
            "total_alive": 0
        }
        
        try:
            network = ipaddress.IPv4Network(cidr, strict=False)
            
            if scan_type == "ping" and SCAPY_AVAILABLE:
                # ICMP ping scan
                for ip in network.hosts():
                    results["total_scanned"] += 1
                    
                    pkt = IP(dst=str(ip))/ICMP()
                    resp = sr1(pkt, timeout=1, verbose=False)
                    
                    if resp:
                        host = NetworkNode(ip=str(ip), node_type="host")
                        
                        # Try hostname resolution
                        try:
                            hostname = socket.gethostbyaddr(str(ip))[0]
                            host.hostname = hostname
                        except:
                            pass
                        
                        self.discovered_hosts[host.ip] = host
                        results["hosts"].append(host)
                        results["total_alive"] += 1
            
            elif scan_type == "comprehensive" and NMAP_AVAILABLE:
                # Use nmap for comprehensive scan
                nm = nmap.PortScanner()
                nm.scan(hosts=cidr, arguments='-sV -O --script=banner')
                
                for host in nm.all_hosts():
                    results["total_scanned"] += 1
                    
                    if nm[host].state() == "up":
                        node = NetworkNode(
                            ip=host,
                            hostname=nm[host].hostname() if nm[host].hostname() else None,
                            node_type="host",
                            os=self._extract_os(nm[host]) if 'osmatch' in nm[host] else None
                        )
                        
                        # Extract services
                        for proto in nm[host].all_protocols():
                            ports = nm[host][proto].keys()
                            for port in ports:
                                service_info = nm[host][proto][port]
                                node.services.append({
                                    "port": port,
                                    "protocol": proto,
                                    "state": service_info['state'],
                                    "service": service_info['name'],
                                    "product": service_info.get('product', ''),
                                    "version": service_info.get('version', ''),
                                    "extrainfo": service_info.get('extrainfo', '')
                                })
                        
                        self.discovered_hosts[node.ip] = node
                        results["hosts"].append(node)
                        results["total_alive"] += 1
            
            # Ingest discovered hosts
            for host in results["hosts"]:
                await self._ingest_network_node(host)
            
        except Exception as e:
            results["error"] = str(e)
        
        return results
    
    def _extract_os(self, host_data: Dict[str, Any]) -> str:
        """Extract OS information from nmap scan"""
        if 'osmatch' in host_data and host_data['osmatch']:
            return host_data['osmatch'][0]['name']
        return "Unknown"
    
    async def trace_route(self, target: str, max_hops: int = 30) -> List[NetworkNode]:
        """
        Trace network route to target and discover intermediate hops.
        """
        route = []
        
        if not SCAPY_AVAILABLE:
            return route
        
        try:
            for ttl in range(1, max_hops + 1):
                pkt = IP(dst=target, ttl=ttl)/ICMP()
                resp = sr1(pkt, timeout=2, verbose=False)
                
                if resp is None:
                    continue
                
                hop = NetworkNode(
                    ip=resp.src,
                    node_type="router",
                    metadata={"ttl": ttl, "rtt": resp.time}
                )
                
                # Try to resolve hostname
                try:
                    hostname = socket.gethostbyaddr(resp.src)[0]
                    hop.hostname = hostname
                except:
                    pass
                
                route.append(hop)
                self.discovered_hosts[hop.ip] = hop
                
                # Create link between hops
                if len(route) > 1:
                    link = NetworkLink(
                        source=route[-2].ip,
                        target=hop.ip,
                        link_type="route",
                        protocol="ip",
                        metadata={"hop": ttl}
                    )
                    self.discovered_links.append(link)
                
                # Check if we reached destination
                if resp.src == target or resp.type == 0:
                    break
            
            # Ingest route into memory
            for hop in route:
                await self._ingest_network_node(hop)
            
            for link in self.discovered_links:
                await self._ingest_network_link(link)
            
        except Exception as e:
            print(f"Traceroute error: {e}")
        
        return route
    
    async def discover_network_services(self, ip: str, port_range: str = "1-1000") -> NetworkNode:
        """
        Discover services running on a specific host.
        """
        node = self.discovered_hosts.get(ip) or NetworkNode(ip=ip)
        
        if not NMAP_AVAILABLE:
            return node
        
        try:
            nm = nmap.PortScanner()
            nm.scan(ip, port_range, arguments='-sV --script=banner,ssl-cert')
            
            if ip in nm.all_hosts():
                host_data = nm[ip]
                
                # Update node info
                if host_data.hostname():
                    node.hostname = host_data.hostname()
                
                # Extract services
                for proto in host_data.all_protocols():
                    ports = host_data[proto].keys()
                    for port in ports:
                        service_info = host_data[proto][port]
                        
                        service = {
                            "port": port,
                            "protocol": proto,
                            "state": service_info['state'],
                            "service": service_info['name'],
                            "product": service_info.get('product', ''),
                            "version": service_info.get('version', ''),
                            "cpe": service_info.get('cpe', ''),
                            "scripts": {}
                        }
                        
                        # Extract script results
                        if 'script' in service_info:
                            service['scripts'] = service_info['script']
                        
                        node.services.append(service)
                
                self.discovered_hosts[ip] = node
                await self._ingest_network_node(node)
        
        except Exception as e:
            print(f"Service discovery error: {e}")
        
        return node
    
    # ==================== DNS and Domain Discovery ====================
    
    async def discover_dns_records(self, domain: str) -> Dict[str, Any]:
        """
        Discover DNS records for a domain.
        """
        records = {
            "domain": domain,
            "A": [],
            "AAAA": [],
            "MX": [],
            "NS": [],
            "TXT": [],
            "CNAME": [],
            "SOA": None
        }
        
        try:
            resolver = dns.resolver.Resolver()
            
            # A records
            try:
                answers = resolver.resolve(domain, 'A')
                records["A"] = [str(rdata) for rdata in answers]
            except:
                pass
            
            # AAAA records
            try:
                answers = resolver.resolve(domain, 'AAAA')
                records["AAAA"] = [str(rdata) for rdata in answers]
            except:
                pass
            
            # MX records
            try:
                answers = resolver.resolve(domain, 'MX')
                records["MX"] = [{"preference": rdata.preference, "exchange": str(rdata.exchange)} 
                               for rdata in answers]
            except:
                pass
            
            # NS records
            try:
                answers = resolver.resolve(domain, 'NS')
                records["NS"] = [str(rdata) for rdata in answers]
            except:
                pass
            
            # TXT records
            try:
                answers = resolver.resolve(domain, 'TXT')
                records["TXT"] = [str(rdata) for rdata in answers]
            except:
                pass
            
            # SOA record
            try:
                answers = resolver.resolve(domain, 'SOA')
                soa = answers[0]
                records["SOA"] = {
                    "mname": str(soa.mname),
                    "rname": str(soa.rname),
                    "serial": soa.serial
                }
            except:
                pass
            
            # Ingest DNS records into memory
            await self._ingest_dns_records(domain, records)
            
        except Exception as e:
            records["error"] = str(e)
        
        return records
    
    async def discover_subdomains(self, domain: str, wordlist: Optional[List[str]] = None) -> List[str]:
        """
        Discover subdomains through brute force and various techniques.
        """
        subdomains = set()
        
        # Default common subdomains
        if wordlist is None:
            wordlist = ['www', 'mail', 'ftp', 'admin', 'blog', 'dev', 'staging', 
                       'api', 'cdn', 'test', 'portal', 'vpn', 'remote']
        
        # Brute force subdomain enumeration
        for prefix in wordlist:
            subdomain = f"{prefix}.{domain}"
            try:
                answers = dns.resolver.resolve(subdomain, 'A')
                if answers:
                    subdomains.add(subdomain)
                    
                    # Discover DNS records for found subdomain
                    await self.discover_dns_records(subdomain)
            except:
                pass
        
        # Certificate transparency logs (simplified)
        # In production, query crt.sh or similar services
        
        return list(subdomains)
    
    async def whois_lookup(self, domain: str) -> Dict[str, Any]:
        """
        Perform WHOIS lookup for domain information.
        """
        if domain in self.whois_cache:
            return self.whois_cache[domain]
        
        whois_data = {
            "domain": domain,
            "registrar": None,
            "creation_date": None,
            "expiration_date": None,
            "name_servers": [],
            "status": []
        }
        
        try:
            import whois
            w = whois.whois(domain)
            
            whois_data["registrar"] = w.registrar
            whois_data["creation_date"] = str(w.creation_date) if w.creation_date else None
            whois_data["expiration_date"] = str(w.expiration_date) if w.expiration_date else None
            whois_data["name_servers"] = w.name_servers if w.name_servers else []
            whois_data["status"] = w.status if w.status else []
            whois_data["emails"] = w.emails if hasattr(w, 'emails') and w.emails else []
            
            self.whois_cache[domain] = whois_data
            
            # Ingest WHOIS data
            await self._ingest_whois_data(domain, whois_data)
            
        except Exception as e:
            whois_data["error"] = str(e)
        
        return whois_data
    
    # ==================== Website and Web Application Discovery ====================
    async def discover_website(self, url: str, max_depth: int = 2, max_pages: int = 100) -> Dict[str, Any]:
        """
        Discover website structure, pages, and assets with proper ID linking.
        """
        import uuid
        from collections import defaultdict
        
        parsed_url = urlparse(url)
        base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        results = {
            "url": url,
            "base_domain": base_domain,
            "pages": [],
            "assets": [],
            "technologies": set(),
            "forms": [],
            "apis": [],
            "relationships": []  # Track parent-child relationships
        }
        
        visited = set()
        to_visit = [(url, 0)]  # (url, depth)
        
        # Generate website ID
        website_id = self._generate_id(url)
        
        # Track page IDs for linking
        page_ids = {}  # url -> page_id
        
        while to_visit and len(visited) < max_pages:
            current_url, depth = to_visit.pop(0)
            
            if current_url in visited or depth > max_depth:
                continue
            
            visited.add(current_url)
            
            try:
                response = requests.get(current_url, timeout=10, allow_redirects=True)
                
                # Generate unique ID for this page
                page_id = self._generate_id(current_url)
                page_ids[current_url] = page_id
                
                # Create web asset with ID
                asset = WebAsset(
                    id=page_id,
                    name=current_url,
                    url=current_url,
                    asset_type="page",
                    status_code=response.status_code,
                    content_type=response.headers.get('Content-Type'),
                    size=len(response.content),
                    headers=dict(response.headers),
                    # website_id=website_id,  # Link to parent website
                    # parent_id=None  # Root pages have no parent
                )
                
                # Analyze security headers
                asset.security_headers = self._analyze_security_headers(response.headers)
                
                # Parse HTML
                if 'text/html' in response.headers.get('Content-Type', ''):
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Detect technologies
                    techs = self._detect_technologies(soup, response.headers)
                    asset.technologies = list(techs)
                    results["technologies"].update(techs)
                    
                    # Find links
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        absolute_url = urljoin(current_url, href)
                        
                        # Only crawl same domain
                        if absolute_url.startswith(base_domain) and absolute_url not in visited:
                            to_visit.append((absolute_url, depth + 1))
                    
                    # Find forms
                    for form in soup.find_all('form'):
                        form_data = {
                            "id": self._generate_id(current_url + str(form)),
                            "page_id": page_id,  # Link form to page
                            "action": urljoin(current_url, form.get('action', '')),
                            "method": form.get('method', 'get').upper(),
                            "inputs": []
                        }
                        
                        for input_tag in form.find_all('input'):
                            form_data["inputs"].append({
                                "name": input_tag.get('name'),
                                "type": input_tag.get('type', 'text')
                            })
                        
                        results["forms"].append(form_data)
                    
                    # Find external resources with proper parent linking
                    for tag, attr in [('img', 'src'), ('script', 'src'), ('link', 'href')]:
                        for element in soup.find_all(tag):
                            if element.get(attr):
                                resource_url = urljoin(current_url, element[attr])
                                resource_id = self._generate_id(resource_url)
                                
                                resource_asset = WebAsset(
                                    id=resource_id,
                                    name=resource_url,
                                    url=resource_url,
                                    asset_type=tag,
                                    # parent_id=page_id,  # Link asset to parent page
                                    # website_id=website_id,
                                    metadata={
                                        "page": current_url,
                                        "page_id": page_id,
                                        "html_tag": tag
                                    }
                                )
                                
                                # Store relationship
                                results["relationships"].append({
                                    # "parent_id": page_id,
                                    "child_id": resource_id,
                                    "relationship_type": f"contains_{tag}",
                                    "source_url": current_url,
                                    "target_url": resource_url
                                })
                                
                                results["assets"].append(resource_asset)
                                
                                # Ingest with proper linking
                                self._ingest_web_asset(resource_asset)
                                self._ingest_website_link(page_id, resource_id, tag)
                                self.discovered_web_assets[resource_url] = resource_asset
                
                results["pages"].append(asset)
                
                # Ingest web asset with ID
                self._ingest_web_asset(asset)
                self._ingest_website_link(website_id, page_id, "page")
                self.discovered_web_assets[current_url] = asset
                
            except Exception as e:
                print(f"Error crawling {current_url}: {e}")
        
        results["technologies"] = list(results["technologies"])
        results["website_id"] = website_id
        
        # Ingest website structure with IDs
        self._ingest_website_structure(base_domain, results)
        self.discovered_websites[base_domain] = results
        
        return results
    def _analyze_security_headers(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """Analyze security-related HTTP headers"""
        security_analysis = {
            "strict_transport_security": headers.get('Strict-Transport-Security'),
            "content_security_policy": headers.get('Content-Security-Policy'),
            "x_frame_options": headers.get('X-Frame-Options'),
            "x_content_type_options": headers.get('X-Content-Type-Options'),
            "x_xss_protection": headers.get('X-XSS-Protection'),
            "referrer_policy": headers.get('Referrer-Policy'),
            "permissions_policy": headers.get('Permissions-Policy'),
            "missing_headers": []
        }
        
        # Check for missing security headers
        required_headers = ['Strict-Transport-Security', 'Content-Security-Policy', 
                          'X-Frame-Options', 'X-Content-Type-Options']
        for header in required_headers:
            if header not in headers:
                security_analysis["missing_headers"].append(header)
        
        return security_analysis
    
    def _detect_technologies(self, soup: BeautifulSoup, headers: Dict[str, str]) -> Set[str]:
        """Detect web technologies used"""
        technologies = set()
        
        # Server header
        if 'Server' in headers:
            technologies.add(headers['Server'])
        
        # X-Powered-By header
        if 'X-Powered-By' in headers:
            technologies.add(headers['X-Powered-By'])
        
        # Meta generator tags
        for meta in soup.find_all('meta', attrs={'name': 'generator'}):
            if meta.get('content'):
                technologies.add(meta['content'])
        
        # Common JavaScript libraries
        for script in soup.find_all('script', src=True):
            src = script['src'].lower()
            if 'jquery' in src:
                technologies.add('jQuery')
            elif 'react' in src:
                technologies.add('React')
            elif 'angular' in src:
                technologies.add('Angular')
            elif 'vue' in src:
                technologies.add('Vue.js')
            elif 'bootstrap' in src:
                technologies.add('Bootstrap')
        
        # WordPress detection
        if soup.find('link', href=re.compile('wp-content')) or soup.find('script', src=re.compile('wp-')):
            technologies.add('WordPress')
        
        return technologies
    
    async def scan_ssl_certificate(self, hostname: str, port: int = 443) -> Dict[str, Any]:
        """
        Scan SSL/TLS certificate information.
        """
        cert_info = {
            "hostname": hostname,
            "port": port,
            "valid": False,
            "issuer": {},
            "subject": {},
            "version": None,
            "serial_number": None,
            "not_before": None,
            "not_after": None,
            "san": []
        }
        
        try:
            context = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    
                    cert_info["valid"] = True
                    cert_info["version"] = cert.get('version')
                    cert_info["serial_number"] = cert.get('serialNumber')
                    cert_info["not_before"] = cert.get('notBefore')
                    cert_info["not_after"] = cert.get('notAfter')
                    
                    # Issuer
                    for item in cert.get('issuer', []):
                        for key, value in item:
                            cert_info["issuer"][key] = value
                    
                    # Subject
                    for item in cert.get('subject', []):
                        for key, value in item:
                            cert_info["subject"][key] = value
                    
                    # Subject Alternative Names
                    if 'subjectAltName' in cert:
                        cert_info["san"] = [name for type, name in cert['subjectAltName']]
                    
                    # Ingest certificate info
                    await self._ingest_ssl_certificate(hostname, cert_info)
        
        except Exception as e:
            cert_info["error"] = str(e)
        
        return cert_info
    
    # ==================== Cloud Infrastructure Discovery ====================
    
    async def discover_aws_infrastructure(self, region: str = 'us-east-1') -> Dict[str, Any]:
        """
        Discover AWS infrastructure (VPCs, EC2, RDS, etc.)
        """
        if not AWS_AVAILABLE:
            return {"error": "boto3 not available"}
        
        results = {
            "provider": "aws",
            "region": region,
            "vpcs": [],
            "ec2_instances": [],
            "rds_instances": [],
            "load_balancers": [],
            "s3_buckets": []
        }
        
        try:
            # EC2 client
            ec2 = boto3.client('ec2', region_name=region)
            
            # Discover VPCs
            vpcs = ec2.describe_vpcs()
            for vpc in vpcs['Vpcs']:
                vpc_data = NetworkSegment(
                    cidr=vpc['CidrBlock'],
                    name=self._get_tag_value(vpc.get('Tags', []), 'Name') or vpc['VpcId'],
                    segment_type="cloud_vpc",
                    metadata={
                        "vpc_id": vpc['VpcId'],
                        "state": vpc['State'],
                        "is_default": vpc['IsDefault'],
                        "provider": "aws",
                        "region": region
                    }
                )
                results["vpcs"].append(vpc_data)
                await self._ingest_network_segment(vpc_data)
            
            # Discover EC2 instances
            instances = ec2.describe_instances()
            for reservation in instances['Reservations']:
                for instance in reservation['Instances']:
                    resource = CloudResource(
                        resource_id=instance['InstanceId'],
                        resource_type="ec2_instance",
                        provider="aws",
                        region=region,
                        zone=instance.get('Placement', {}).get('AvailabilityZone'),
                        state=instance['State']['Name'],
                        tags={tag['Key']: tag['Value'] for tag in instance.get('Tags', [])},
                        configuration={
                            "instance_type": instance['InstanceType'],
                            "private_ip": instance.get('PrivateIpAddress'),
                            "public_ip": instance.get('PublicIpAddress'),
                            "vpc_id": instance.get('VpcId'),
                            "subnet_id": instance.get('SubnetId'),
                            "security_groups": [sg['GroupId'] for sg in instance.get('SecurityGroups', [])]
                        }
                    )
                    results["ec2_instances"].append(resource)
                    await self._ingest_cloud_resource(resource)
            
            # Discover RDS instances
            rds = boto3.client('rds', region_name=region)
            db_instances = rds.describe_db_instances()
            for db in db_instances['DBInstances']:
                resource = CloudResource(
                    resource_id=db['DBInstanceIdentifier'],
                    resource_type="rds_instance",
                    provider="aws",
                    region=region,
                    zone=db.get('AvailabilityZone'),
                    state=db['DBInstanceStatus'],
                    configuration={
                        "engine": db['Engine'],
                        "engine_version": db['EngineVersion'],
                        "instance_class": db['DBInstanceClass'],
                        "endpoint": db.get('Endpoint', {}).get('Address'),
                        "port": db.get('Endpoint', {}).get('Port'),
                        "vpc_id": db.get('DBSubnetGroup', {}).get('VpcId')
                    }
                )
                results["rds_instances"].append(resource)
                await self._ingest_cloud_resource(resource)
            
            # Discover Load Balancers
            elb = boto3.client('elbv2', region_name=region)
            lbs = elb.describe_load_balancers()
            for lb in lbs['LoadBalancers']:
                resource = CloudResource(
                    resource_id=lb['LoadBalancerArn'],
                    resource_type="load_balancer",
                    provider="aws",
                    region=region,
                    state=lb['State']['Code'],
                    configuration={
                        "name": lb['LoadBalancerName'],
                        "type": lb['Type'],
                        "scheme": lb['Scheme'],
                        "dns_name": lb['DNSName'],
                        "vpc_id": lb['VpcId'],
                        "availability_zones": [az['ZoneName'] for az in lb.get('AvailabilityZones', [])]
                    }
                )
                results["load_balancers"].append(resource)
                await self._ingest_cloud_resource(resource)
            
            # Discover S3 buckets
            s3 = boto3.client('s3')
            buckets = s3.list_buckets()
            for bucket in buckets['Buckets']:
                resource = CloudResource(
                    resource_id=bucket['Name'],
                    resource_type="s3_bucket",
                    provider="aws",
                    region=region,
                    configuration={
                        "creation_date": str(bucket['CreationDate'])
                    }
                )
                results["s3_buckets"].append(resource)
                await self._ingest_cloud_resource(resource)
        
        except Exception as e:
            results["error"] = str(e)
        
        return results
    
    def _get_tag_value(self, tags: List[Dict], key: str) -> Optional[str]:
        """Extract tag value from AWS tags list"""
        for tag in tags:
            if tag.get('Key') == key:
                return tag.get('Value')
        return None
    
    async def discover_azure_infrastructure(self, subscription_id: str) -> Dict[str, Any]:
        """
        Discover Azure infrastructure (VNets, VMs, etc.)
        """
        if not AZURE_AVAILABLE:
            return {"error": "Azure SDK not available"}
        
        results = {
            "provider": "azure",
            "subscription_id": subscription_id,
            "vnets": [],
            "vms": [],
            "databases": []
        }
        
        try:
            credential = DefaultAzureCredential()
            network_client = NetworkManagementClient(credential, subscription_id)
            compute_client = ComputeManagementClient(credential, subscription_id)
            
            # Discover Virtual Networks
            for vnet in network_client.virtual_networks.list_all():
                vnet_data = NetworkSegment(
                    cidr=vnet.address_space.address_prefixes[0] if vnet.address_space.address_prefixes else None,
                    name=vnet.name,
                    segment_type="cloud_vnet",
                    metadata={
                        "vnet_id": vnet.id,
                        "location": vnet.location,
                        "provider": "azure",
                        "resource_group": vnet.id.split('/')[4]
                    }
                )
                results["vnets"].append(vnet_data)
                await self._ingest_network_segment(vnet_data)
            
            # Discover Virtual Machines
            for vm in compute_client.virtual_machines.list_all():
                resource = CloudResource(
                    resource_id=vm.id,
                    resource_type="virtual_machine",
                    provider="azure",
                    region=vm.location,
                    configuration={
                        "name": vm.name,
                        "vm_size": vm.hardware_profile.vm_size if vm.hardware_profile else None,
                        "os_type": vm.storage_profile.os_disk.os_type if vm.storage_profile and vm.storage_profile.os_disk else None,
                        "resource_group": vm.id.split('/')[4]
                    }
                )
                results["vms"].append(resource)
                await self._ingest_cloud_resource(resource)
        
        except Exception as e:
            results["error"] = str(e)
        
        return results
    
    async def discover_gcp_infrastructure(self, project_id: str) -> Dict[str, Any]:
        """
        Discover GCP infrastructure (VPCs, Compute Engine, etc.)
        """
        if not GCP_AVAILABLE:
            return {"error": "GCP SDK not available"}
        
        results = {
            "provider": "gcp",
            "project_id": project_id,
            "networks": [],
            "instances": []
        }
        
        try:
            # Discover Compute Engine instances
            instances_client = compute_v1.InstancesClient()
            
            # List all zones
            zones_client = compute_v1.ZonesClient()
            zones_request = compute_v1.ListZonesRequest(project=project_id)
            zones = zones_client.list(request=zones_request)
            
            for zone in zones:
                request = compute_v1.ListInstancesRequest(
                    project=project_id,
                    zone=zone.name
                )
                
                for instance in instances_client.list(request=request):
                    resource = CloudResource(
                        resource_id=str(instance.id),
                        resource_type="compute_instance",
                        provider="gcp",
                        region=zone.region.split('/')[-1] if zone.region else None,
                        zone=zone.name,
                        state=instance.status,
                        configuration={
                            "name": instance.name,
                            "machine_type": instance.machine_type.split('/')[-1],
                            "network_interfaces": [
                                {
                                    "network": ni.network,
                                    "internal_ip": ni.network_i_p,
                                    "external_ip": ni.access_configs[0].nat_i_p if ni.access_configs else None
                                }
                                for ni in instance.network_interfaces
                            ]
                        }
                    )
                    results["instances"].append(resource)
                    await self._ingest_cloud_resource(resource)
        
        except Exception as e:
            results["error"] = str(e)
        
        return results
    
    async def discover_kubernetes_cluster(self, context_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Discover Kubernetes cluster resources (pods, services, deployments, etc.)
        """
        if not K8S_AVAILABLE:
            return {"error": "Kubernetes client not available"}
        
        results = {
            "provider": "kubernetes",
            "context": context_name,
            "namespaces": [],
            "pods": [],
            "services": [],
            "deployments": [],
            "ingresses": []
        }
        
        try:
            # Load kubeconfig
            if context_name:
                config.load_kube_config(context=context_name)
            else:
                config.load_kube_config()
            
            v1 = client.CoreV1Api()
            apps_v1 = client.AppsV1Api()
            networking_v1 = client.NetworkingV1Api()
            
            # Discover Namespaces
            for ns in v1.list_namespace().items:
                results["namespaces"].append(ns.metadata.name)
            
            # Discover Pods
            for pod in v1.list_pod_for_all_namespaces().items:
                resource = CloudResource(
                    resource_id=f"{pod.metadata.namespace}/{pod.metadata.name}",
                    resource_type="pod",
                    provider="kubernetes",
                    state=pod.status.phase,
                    configuration={
                        "namespace": pod.metadata.namespace,
                        "name": pod.metadata.name,
                        "labels": pod.metadata.labels,
                        "node": pod.spec.node_name,
                        "pod_ip": pod.status.pod_ip,
                        "containers": [
                            {
                                "name": c.name,
                                "image": c.image
                            }
                            for c in pod.spec.containers
                        ]
                    }
                )
                results["pods"].append(resource)
                await self._ingest_cloud_resource(resource)
            
            # Discover Services
            for svc in v1.list_service_for_all_namespaces().items:
                resource = CloudResource(
                    resource_id=f"{svc.metadata.namespace}/{svc.metadata.name}",
                    resource_type="service",
                    provider="kubernetes",
                    configuration={
                        "namespace": svc.metadata.namespace,
                        "name": svc.metadata.name,
                        "type": svc.spec.type,
                        "cluster_ip": svc.spec.cluster_ip,
                        "external_ips": svc.spec.external_i_ps or [],
                        "ports": [
                            {
                                "port": p.port,
                                "target_port": p.target_port,
                                "protocol": p.protocol
                            }
                            for p in svc.spec.ports
                        ] if svc.spec.ports else []
                    }
                )
                results["services"].append(resource)
                await self._ingest_cloud_resource(resource)
            
            # Discover Deployments
            for dep in apps_v1.list_deployment_for_all_namespaces().items:
                resource = CloudResource(
                    resource_id=f"{dep.metadata.namespace}/{dep.metadata.name}",
                    resource_type="deployment",
                    provider="kubernetes",
                    configuration={
                        "namespace": dep.metadata.namespace,
                        "name": dep.metadata.name,
                        "replicas": dep.spec.replicas,
                        "available_replicas": dep.status.available_replicas,
                        "labels": dep.metadata.labels
                    }
                )
                results["deployments"].append(resource)
                await self._ingest_cloud_resource(resource)
            
            # Discover Ingresses
            for ing in networking_v1.list_ingress_for_all_namespaces().items:
                resource = CloudResource(
                    resource_id=f"{ing.metadata.namespace}/{ing.metadata.name}",
                    resource_type="ingress",
                    provider="kubernetes",
                    configuration={
                        "namespace": ing.metadata.namespace,
                        "name": ing.metadata.name,
                        "rules": [
                            {
                                "host": rule.host,
                                "paths": [
                                    {
                                        "path": path.path,
                                        "backend": f"{path.backend.service.name}:{path.backend.service.port.number}"
                                    }
                                    for path in rule.http.paths
                                ] if rule.http else []
                            }
                            for rule in ing.spec.rules
                        ] if ing.spec.rules else []
                    }
                )
                results["ingresses"].append(resource)
                await self._ingest_cloud_resource(resource)
        
        except Exception as e:
            results["error"] = str(e)
        
        return results
    
    async def discover_docker_containers(self) -> Dict[str, Any]:
        """
        Discover Docker containers on local host.
        """
        if not DOCKER_AVAILABLE:
            return {"error": "Docker SDK not available"}
        
        results = {
            "provider": "docker",
            "containers": [],
            "images": [],
            "networks": [],
            "volumes": []
        }
        
        try:
            docker_client = docker.from_env()
            
            # Discover Containers
            for container in docker_client.containers.list(all=True):
                resource = CloudResource(
                    resource_id=container.id,
                    resource_type="container",
                    provider="docker",
                    state=container.status,
                    configuration={
                        "name": container.name,
                        "image": container.image.tags[0] if container.image.tags else None,
                        "ports": container.ports,
                        "labels": container.labels,
                        "networks": list(container.attrs['NetworkSettings']['Networks'].keys())
                    }
                )
                results["containers"].append(resource)
                await self._ingest_cloud_resource(resource)
            
            # Discover Networks
            for network in docker_client.networks.list():
                net_segment = NetworkSegment(
                    cidr=network.attrs['IPAM']['Config'][0]['Subnet'] if network.attrs['IPAM']['Config'] else None,
                    name=network.name,
                    segment_type="docker_network",
                    metadata={
                        "network_id": network.id,
                        "driver": network.attrs['Driver'],
                        "scope": network.attrs['Scope']
                    }
                )
                results["networks"].append(net_segment)
                await self._ingest_network_segment(net_segment)
            
            # Discover Images
            for image in docker_client.images.list():
                for tag in image.tags:
                    resource = CloudResource(
                        resource_id=image.id,
                        resource_type="container_image",
                        provider="docker",
                        configuration={
                            "tag": tag,
                            "size": image.attrs['Size'],
                            "created": image.attrs['Created']
                        }
                    )
                    results["images"].append(resource)
                    await self._ingest_cloud_resource(resource)
        
        except Exception as e:
            results["error"] = str(e)
        
        return results
    
    # ==================== Ingestion into Memory System ====================
    
    async def _ingest_network_node(self, node: NetworkNode):
        """Ingest network node into memory graph"""
        entity_id = self._generate_id(f"host_{node.ip}")
        
        properties = {
            "name": node.name or node.ip,
            "ip": node.ip,
            "hostname": node.hostname,
            # "mac": node.mac,
            "node_type": node.node_type,
            # "os": node.os,
            # "vendor": node.vendor,
            "services": node.services,
            # **node.metadata
            "created_at": datetime.now().isoformat(),
        }
        
        try:
            self.memory.upsert_entity(
                entity_id=entity_id,
                etype="network_host",
                labels=["NetworkHost", node.node_type.capitalize()],
                properties=properties
            )
        except Exception as e:
            print(f"Error ingesting network node {node.ip}: {e}")
        
        # Create service nodes for each discovered service
        for service in node.services:
            service_id = self._generate_id(f"service_{node.ip}_{service['port']}_{service['protocol']}")
            
            self.memory.upsert_entity(
                entity_id=service_id,
                etype="network_service",
                labels=["NetworkService", service.get('service', 'unknown').upper()],
                properties={
                    "name": f"{node.ip}:{service['port']}/{service['protocol']}",
                    "created_at": datetime.now().isoformat(),
                    "port": service['port'],
                    "protocol": service['protocol'],
                    "state": service.get('state'),
                    "service_name": service.get('service'),
                    "product": service.get('product'),
                    "version": service.get('version'),
                    "cpe": service.get('cpe')
                }
            )
            
            # Link service to host
            self.memory.link(entity_id, service_id, "RUNS_SERVICE", {
                "discovered_at": datetime.now().isoformat()
            })
    
    async def _ingest_network_link(self, link: NetworkLink):
        """Ingest network link into memory graph"""
        src_id = self._generate_id(f"host_{link.source}")
        dst_id = self._generate_id(f"host_{link.target}")
        
        self.memory.link(
            src_id,
            dst_id,
            f"CONNECTS_TO_{link.link_type.upper()}",
            {
                "protocol": link.protocol,
                "port": link.port,
                "bandwidth": link.bandwidth,
                "latency": link.latency,
                **link.metadata
            }
        )
        
    def _ingest_website_link(self, src, dst, tags):
        """Ingest network link into memory graph"""
        # src_id = self._generate_id(f"host_{link.source}")
        # dst_id = self._generate_id(f"host_{link.target}")
        print(f"[INGESTOR] Linking {src} to {dst} with tags {tags}")
        try:
            self.memory.link_by_property(
                "id",
                src,
                "id",
                dst,
                tags.upper(),
                # {
                #     "protocol": link.protocol,
                #     "port": link.port,
                #     "bandwidth": link.bandwidth,
                #     "latency": link.latency,
                #     **link.metadata
                # }
            )
        except Exception as e:
            print(f"Error linking {src} to {dst}: {e}")
    async def _ingest_network_segment(self, segment: NetworkSegment):
        """Ingest network segment into memory graph"""
        entity_id = self._generate_id(f"segment_{segment.cidr}")
        
        self.memory.upsert_entity(
            entity_id=entity_id,
            etype="network_segment",
            labels=["NetworkSegment", segment.segment_type.upper()],
            properties={
                "name": segment.name or segment.cidr,
                "created_at": datetime.now().isoformat(),
                "cidr": segment.cidr,
                "name": segment.name,
                "vlan": segment.vlan,
                "segment_type": segment.segment_type,
                "gateway": segment.gateway,
                "dns_servers": segment.dns_servers,
                "dhcp_range": segment.dhcp_range,
                **segment.metadata
            }
        )
    
    async def _ingest_network_topology(self, topology: Dict[str, Any]):
        """Ingest complete network topology"""
        # Create network entity
        network_id = self._generate_id(f"network_{topology.get('network', 'unknown')}")
        
        self.memory.upsert_entity(
            entity_id=network_id,
            etype="network",
            labels=["Network"],
            properties={
                "name": topology.get("name", "Discovered Network"),
                "created_at": datetime.now().isoformat(),
                "cidr": topology.get("network"),
                "discovered_at": datetime.now().isoformat(),
                "total_hosts": len(topology.get("hosts", []))
            }
        )
        
        # Link all hosts to network
        for host in topology.get("hosts", []):
            host_id = self._generate_id(f"host_{host.ip}")
            self.memory.link(network_id, host_id, "CONTAINS_HOST")
        
        # Link all segments to network
        for segment in topology.get("segments", []):
            segment_id = self._generate_id(f"segment_{segment.cidr}")
            self.memory.link(network_id, segment_id, "HAS_SEGMENT")
    
    async def _ingest_dns_records(self, domain: str, records: Dict[str, Any]):
        """Ingest DNS records into memory graph"""
        domain_id = self._generate_id(f"domain_{domain}")
        
        self.memory.upsert_entity(
            entity_id=domain_id,
            etype="domain",
            labels=["Domain"],
            properties={
                "name": domain,
                "created_at": datetime.now().isoformat(),
                "domain": domain,
                "dns_records": records
            }
        )
        
        # Create host entities for A records
        for ip in records.get("A", []):
            host_id = self._generate_id(f"host_{ip}")
            self.memory.link(domain_id, host_id, "RESOLVES_TO", {"record_type": "A"})
        
        # Create entities for name servers
        for ns in records.get("NS", []):
            ns_id = self._generate_id(f"nameserver_{ns}")
            self.memory.upsert_entity(
                entity_id=ns_id,
                etype="nameserver",
                labels=["Nameserver"],
                properties={
                    "name": ns,
                    "hostname": ns
                    }
            )
            self.memory.link(domain_id, ns_id, "USES_NAMESERVER")
    
    async def _ingest_whois_data(self, domain: str, whois_data: Dict[str, Any]):
        """Ingest WHOIS data into memory graph"""
        domain_id = self._generate_id(f"domain_{domain}")
        
        # Update domain entity with WHOIS data
        self.memory.upsert_entity(
            entity_id=domain_id,
            etype="domain",
            properties={
                "name": f"whois_{domain}",
                "created_at": datetime.now().isoformat(),
                "registrar": whois_data.get("registrar"),
                "creation_date": whois_data.get("creation_date"),
                "expiration_date": whois_data.get("expiration_date"),
                "whois_status": whois_data.get("status")
            }
        )
        
        # Create registrar entity
        if whois_data.get("registrar"):
            registrar_id = self._generate_id(f"registrar_{whois_data['registrar']}")
            self.memory.upsert_entity(
                entity_id=registrar_id,
                etype="registrar",
                labels=["Registrar"],
                properties={"name": whois_data["registrar"]}
            )
            self.memory.link(domain_id, registrar_id, "REGISTERED_WITH")
    
    def _ingest_web_asset(self, asset: WebAsset):
        """Ingest web asset into memory graph"""
        asset_id = self._generate_id(f"asset_{asset.url}")
        print(f"Ingesting web asset: {asset.url} with ID {asset_id}")
        try:
            result = self.memory.upsert_entity(
                entity_id=asset.id or asset_id,
                etype="web_asset",
                labels=["WebAsset", asset.asset_type.capitalize()],
                properties={
                    "name": asset.url,
                    "created_at": datetime.now().isoformat(),
                    "url": asset.url,
                    "asset_type": asset.asset_type,
                    "status_code": asset.status_code,
                    "content_type": asset.content_type,
                    "size": asset.size,
                    # "technologies": asset.technologies,
                    # "security_headers": asset.security_headers,
                    # **asset.metadata
                }
            )
            print(result)
        except Exception as e:
            print(f"Error ingesting web asset {asset.url}: {e}")
        
        # try:    
        #     # Store full content in vector database
        #     if asset.status_code == 200:
        #         doc_id = f"doc_{asset_id}"
        #         self.memory.attach_document(
        #             entity_id=asset_id,
        #             doc_id=doc_id,
        #             text=f"Web asset: {asset.url}\nType: {asset.asset_type}\nStatus: {asset.status_code}",
        #             metadata={"type": "web_asset"}
        #         )
        except Exception as e:
            print(f"Error attaching document for web asset {asset.url}: {e}")
        return result

    def _ingest_website_structure(self, base_domain: str, structure: Dict[str, Any]):
        """Ingest website structure into memory graph"""
        site_id = self._generate_id(f"website_{base_domain}")
        try:
            self.memory.upsert_entity(
                entity_id=structure.get("id", []) or site_id,
                etype="website",
                labels=["Website"],
                properties={
                    "name": base_domain,
                    "created_at": datetime.now().isoformat(),
                    "base_domain": base_domain,
                    "total_pages": len(structure.get("pages", [])),
                    "total_assets": len(structure.get("assets", [])),
                    "technologies": structure.get("technologies", []),
                    "discovered_at": datetime.now().isoformat()
                }
            )
        except Exception as e:
            print(f"Error ingesting website structure {base_domain}: {e}")

        try:        
            # Link pages to website
            for page in structure.get("pages", []):
                page_id = self._generate_id(f"asset_{page.url}")
                self.memory.link(site_id, page_id, "HAS_PAGE")

            # Link domain to website
            parsed = urlparse(base_domain)
            domain_id = self._generate_id(f"domain_{parsed.netloc}")
            self.memory.link(domain_id, site_id, "HOSTS_WEBSITE")
        except Exception as e:
            print(f"Error linking website {base_domain}: {e}")

    async def _ingest_ssl_certificate(self, hostname: str, cert_info: Dict[str, Any]):
        """Ingest SSL certificate into memory graph"""
        cert_id = self._generate_id(f"cert_{hostname}_{cert_info.get('serial_number', '')}")
        
        self.memory.upsert_entity(
            entity_id=cert_id,
            etype="ssl_certificate",
            labels=["SSLCertificate"],
            properties={
                "name": f"cert_{hostname}",
                "created_at": datetime.now().isoformat(),
                "hostname": hostname,
                "issuer": cert_info.get("issuer"),
                "subject": cert_info.get("subject"),
                "valid": cert_info.get("valid"),
                "not_before": cert_info.get("not_before"),
                "not_after": cert_info.get("not_after"),
                "serial_number": cert_info.get("serial_number"),
                "san": cert_info.get("san")
            }
        )
        
        # Link certificate to host
        host_id = self._generate_id(f"host_{hostname}")
        self.memory.link(host_id, cert_id, "HAS_CERTIFICATE")
    
    async def _ingest_cloud_resource(self, resource: CloudResource):
        """Ingest cloud resource into memory graph"""
        entity_id = self._generate_id(f"cloud_{resource.provider}_{resource.resource_id}")
        
        self.memory.upsert_entity(
            entity_id=entity_id,
            etype="cloud_resource",
            labels=["CloudResource", resource.provider.upper(), resource.resource_type.upper()],
            properties={
                "name": f"{resource.provider}_{resource.resource_type}_{resource.resource_id}",
                "created_at": datetime.now().isoformat(),
                "resource_id": resource.resource_id,
                "resource_type": resource.resource_type,
                "provider": resource.provider,
                "region": resource.region,
                "zone": resource.zone,
                "state": resource.state,
                "tags": resource.tags,
                "configuration": resource.configuration,
                **resource.metadata
            }
        )
    
    def _generate_id(self, key: str) -> str:
        """Generate consistent entity ID from key, starting with a timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        hash_part = hashlib.md5(key.encode()).hexdigest()[:16]
        # return f"mem_{timestamp}_{hash_part}"
        return f"{hash_part}"
    
    # ==================== Query and Analytics ====================
    
    def query_network_path(self, source_ip: str, target_ip: str) -> List[NetworkNode]:
        """Query network path between two hosts"""
        src_id = self._generate_id(f"host_{source_ip}")
        dst_id = self._generate_id(f"host_{target_ip}")
        
        subgraph = self.memory.extract_subgraph([src_id, dst_id], depth=5)
        
        # Extract path (simplified)
        # In production, implement graph traversal algorithms (Dijkstra, BFS)
        path_nodes = []
        for node in subgraph.get("nodes", []):
            if "NetworkHost" in node.get("labels", []):
                path_nodes.append(NetworkNode(
                    ip=node["properties"]["ip"],
                    hostname=node["properties"].get("hostname"),
                    node_type=node["properties"].get("node_type", "host")
                ))
        
        return path_nodes
    
    def query_exposed_services(self, port: Optional[int] = None) -> List[Dict[str, Any]]:
        """Query exposed network services"""
        # Use semantic search to find services
        query_text = f"network service port {port}" if port else "network service"
        results = self.memory.semantic_retrieve(query_text, k=50)
        
        services = []
        for result in results:
            if result.get("metadata", {}).get("type") == "network_service":
                services.append(result)
        
        return services
    
    def generate_network_map(self, output_format: str = "json") -> Dict[str, Any]:
        """Generate network topology map"""
        # Query all network entities
        seeds = self.memory.graph.list_subgraph_seeds()
        
        network_map = {
            "nodes": [],
            "links": [],
            "segments": []
        }
        
        # Extract network topology
        # In production, implement proper graph visualization
        
        return network_map


# ==================== CLI Example ====================

async def main():
    """Example usage"""
    # from hybrid_memory import HybridMemory
    
    # Initialize memory system
    memory = HybridMemory(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="",
        chroma_dir="./chroma_db"
    )
    
    ingestor = NetworkInfrastructureIngestor(memory)
    
    # Discover local network
    print("Discovering local network...")
    local_net = await ingestor.discover_local_network()
    print(f"Found {len(local_net['hosts'])} hosts")
    
    # Scan specific host
    print("\nScanning services on 192.168.0.200...")
    host = await ingestor.discover_network_services("192.168.0.200")
    print(f"Found {len(host.services)} services")
    
    # Discover DNS records
    print("\nDiscovering DNS for example.com...")
    dns = await ingestor.discover_dns_records("maxhodl.com")
    print(f"A records: {dns['A']}")
    
    # Discover website
    print("\nDiscovering website structure...")
    website = await ingestor.discover_website("https://maxhodl.com", max_depth=2)
    print(f"Found {len(website['pages'])} pages")
    print(f"Technologies: {website['technologies']}")
    
    # # Discover AWS infrastructure
    # print("\nDiscovering AWS infrastructure...")
    # aws = await ingestor.discover_aws_infrastructure(region='us-east-1')
    # print(f"Found {len(aws['ec2_instances'])} EC2 instances")
    
    # # Discover Kubernetes cluster
    # print("\nDiscovering Kubernetes cluster...")
    # k8s = await ingestor.discover_kubernetes_cluster()
    # print(f"Found {len(k8s['pods'])} pods across {len(k8s['namespaces'])} namespaces")
    
    # Discover Docker containers
    print("\nDiscovering Docker containers...")
    docker = await ingestor.discover_docker_containers()
    if "error" in docker:
        print(f"Error discovering Docker containers: {docker['error']}")
    else:
        print(f"Found {len(docker['containers'])} containers and {len(docker['networks'])} networks")
    
    # Query exposed services
    print("\nQuerying exposed services on port 80...")
    services = ingestor.query_exposed_services(port=80)
    print(f"Found {len(services)} services on port 80")
    
    # Generate network map
    print("\nGenerating network topology map...")
    network_map = ingestor.generate_network_map()
    print(f"Network map: {len(network_map['nodes'])} nodes, {len(network_map['links'])} links")


# if __name__ == "__main__":
#     asyncio.run(main())


# ==================== Advanced Features ====================

class NetworkMonitor:
    """
    Real-time network monitoring and change detection.
    Continuously monitors network and updates memory graph.
    """
    
    def __init__(self, ingestor: NetworkInfrastructureIngestor, interval: int = 300):
        """
        Args:
            ingestor: NetworkInfrastructureIngestor instance
            interval: Monitoring interval in seconds
        """
        self.ingestor = ingestor
        self.interval = interval
        self.running = False
        self.baseline: Dict[str, Any] = {}
    
    async def start_monitoring(self, targets: List[str]):
        """
        Start continuous network monitoring.
        
        Args:
            targets: List of targets to monitor (IPs, domains, networks)
        """
        self.running = True
        
        # Establish baseline
        print("Establishing baseline...")
        self.baseline = await self._scan_targets(targets)
        
        print(f"Monitoring started. Checking every {self.interval}s...")
        
        while self.running:
            await asyncio.sleep(self.interval)
            
            # Scan targets
            current = await self._scan_targets(targets)
            
            # Detect changes
            changes = self._detect_changes(self.baseline, current)
            
            if changes:
                print(f"\nDetected {len(changes)} changes:")
                for change in changes:
                    print(f"  - {change['type']}: {change['description']}")
                    
                    # Ingest change into memory
                    await self._ingest_change(change)
            
            # Update baseline
            self.baseline = current
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.running = False
    
    async def _scan_targets(self, targets: List[str]) -> Dict[str, Any]:
        """Scan all targets and return current state"""
        state = {
            "timestamp": datetime.now().isoformat(),
            "hosts": {},
            "services": {}
        }
        
        for target in targets:
            try:
                # Check if target is IP or domain
                if self._is_ip(target):
                    host = await self.ingestor.discover_network_services(target, port_range="1-1000")
                    state["hosts"][target] = host
                    
                    for service in host.services:
                        service_key = f"{target}:{service['port']}"
                        state["services"][service_key] = service
                else:
                    # Domain - check DNS and web services
                    dns = await self.ingestor.discover_dns_records(target)
                    state["hosts"][target] = {"dns": dns}
            
            except Exception as e:
                print(f"Error scanning {target}: {e}")
        
        return state
    
    def _detect_changes(self, baseline: Dict[str, Any], current: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect changes between baseline and current state"""
        changes = []
        
        # Compare hosts
        baseline_hosts = set(baseline.get("hosts", {}).keys())
        current_hosts = set(current.get("hosts", {}).keys())
        
        # New hosts
        for host in current_hosts - baseline_hosts:
            changes.append({
                "type": "new_host",
                "description": f"New host discovered: {host}",
                "host": host,
                "data": current["hosts"][host]
            })
        
        # Removed hosts
        for host in baseline_hosts - current_hosts:
            changes.append({
                "type": "host_down",
                "description": f"Host went down: {host}",
                "host": host
            })
        
        # Compare services
        baseline_services = set(baseline.get("services", {}).keys())
        current_services = set(current.get("services", {}).keys())
        
        # New services
        for service_key in current_services - baseline_services:
            changes.append({
                "type": "new_service",
                "description": f"New service detected: {service_key}",
                "service": service_key,
                "data": current["services"][service_key]
            })
        
        # Removed services
        for service_key in baseline_services - current_services:
            changes.append({
                "type": "service_down",
                "description": f"Service went down: {service_key}",
                "service": service_key
            })
        
        # Changed services (version updates, etc.)
        for service_key in baseline_services & current_services:
            baseline_svc = baseline["services"][service_key]
            current_svc = current["services"][service_key]
            
            if baseline_svc.get("version") != current_svc.get("version"):
                changes.append({
                    "type": "service_version_change",
                    "description": f"Service version changed: {service_key}",
                    "service": service_key,
                    "old_version": baseline_svc.get("version"),
                    "new_version": current_svc.get("version")
                })
        
        return changes
    
    def _is_ip(self, target: str) -> bool:
        """Check if target is an IP address"""
        try:
            ipaddress.ip_address(target)
            return True
        except ValueError:
            return False
    
    async def _ingest_change(self, change: Dict[str, Any]):
        """Ingest detected change into memory graph"""
        change_id = self.ingestor._generate_id(f"change_{datetime.now().isoformat()}_{change['type']}")
        
        self.ingestor.memory.upsert_entity(
            entity_id=change_id,
            etype="network_change",
            labels=["NetworkChange", change["type"].upper()],
            properties={
                "change_type": change["type"],
                "description": change["description"],
                "timestamp": datetime.now().isoformat(),
                "data": change
            }
        )


class NetworkSecurityAnalyzer:
    """
    Security analysis of discovered network infrastructure.
    Identifies vulnerabilities, misconfigurations, and risks.
    """
    
    def __init__(self, ingestor: NetworkInfrastructureIngestor):
        self.ingestor = ingestor
    
    async def analyze_network_security(self) -> Dict[str, Any]:
        """
        Comprehensive security analysis of discovered network.
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "findings": [],
            "risk_score": 0,
            "recommendations": []
        }
        
        # Check for exposed services
        exposed = self._check_exposed_services()
        if exposed:
            report["findings"].extend(exposed)
        
        # Check for weak SSL/TLS
        ssl_issues = self._check_ssl_issues()
        if ssl_issues:
            report["findings"].extend(ssl_issues)
        
        # Check for missing security headers
        header_issues = self._check_security_headers()
        if header_issues:
            report["findings"].extend(header_issues)
        
        # Check for open ports
        port_issues = self._check_dangerous_ports()
        if port_issues:
            report["findings"].extend(port_issues)
        
        # Check for outdated software
        version_issues = self._check_outdated_versions()
        if version_issues:
            report["findings"].extend(version_issues)
        
        # Calculate risk score
        report["risk_score"] = self._calculate_risk_score(report["findings"])
        
        # Generate recommendations
        report["recommendations"] = self._generate_recommendations(report["findings"])
        
        # Ingest security report
        await self._ingest_security_report(report)
        
        return report
    
    def _check_exposed_services(self) -> List[Dict[str, Any]]:
        """Check for exposed services that shouldn't be public"""
        findings = []
        
        dangerous_services = {
            22: "SSH",
            23: "Telnet",
            3306: "MySQL",
            5432: "PostgreSQL",
            27017: "MongoDB",
            6379: "Redis",
            9200: "Elasticsearch"
        }
        
        services = self.ingestor.query_exposed_services()
        
        for service in services:
            port = service.get("metadata", {}).get("port")
            if port in dangerous_services:
                findings.append({
                    "severity": "HIGH",
                    "category": "exposed_service",
                    "title": f"Exposed {dangerous_services[port]} Service",
                    "description": f"Port {port} ({dangerous_services[port]}) is exposed",
                    "port": port,
                    "service": dangerous_services[port]
                })
        
        return findings
    
    def _check_ssl_issues(self) -> List[Dict[str, Any]]:
        """Check for SSL/TLS issues"""
        findings = []
        
        # Query all SSL certificates from memory
        results = self.ingestor.memory.semantic_retrieve("ssl certificate", k=100)
        
        for cert in results:
            metadata = cert.get("metadata", {})
            
            # Check expiration
            if metadata.get("not_after"):
                try:
                    expiry = datetime.fromisoformat(metadata["not_after"].replace('Z', '+00:00'))
                    days_until_expiry = (expiry - datetime.now()).days
                    
                    if days_until_expiry < 30:
                        findings.append({
                            "severity": "MEDIUM",
                            "category": "ssl_expiring",
                            "title": "SSL Certificate Expiring Soon",
                            "description": f"Certificate expires in {days_until_expiry} days",
                            "hostname": metadata.get("hostname"),
                            "expiry_date": metadata["not_after"]
                        })
                except:
                    pass
        
        return findings
    
    def _check_security_headers(self) -> List[Dict[str, Any]]:
        """Check for missing security headers"""
        findings = []
        
        # Query web assets
        results = self.ingestor.memory.semantic_retrieve("web asset security headers", k=100)
        
        for asset in results:
            security_headers = asset.get("metadata", {}).get("security_headers", {})
            missing = security_headers.get("missing_headers", [])
            
            if missing:
                findings.append({
                    "severity": "MEDIUM",
                    "category": "missing_security_headers",
                    "title": "Missing Security Headers",
                    "description": f"Missing headers: {', '.join(missing)}",
                    "url": asset.get("metadata", {}).get("url"),
                    "missing_headers": missing
                })
        
        return findings
    
    def _check_dangerous_ports(self) -> List[Dict[str, Any]]:
        """Check for commonly exploited ports"""
        findings = []
        
        dangerous_ports = [21, 23, 135, 139, 445, 1433, 3389]
        
        for port in dangerous_ports:
            services = self.ingestor.query_exposed_services(port=port)
            
            if services:
                findings.append({
                    "severity": "HIGH",
                    "category": "dangerous_port",
                    "title": f"Dangerous Port {port} Open",
                    "description": f"Port {port} is open and commonly targeted by attackers",
                    "port": port,
                    "affected_hosts": len(services)
                })
        
        return findings
    
    def _check_outdated_versions(self) -> List[Dict[str, Any]]:
        """Check for outdated software versions"""
        findings = []
        
        # This would integrate with the vulnerability ingestor
        # to cross-reference discovered services with known vulnerabilities
        
        return findings
    
    def _calculate_risk_score(self, findings: List[Dict[str, Any]]) -> int:
        """Calculate overall risk score (0-100)"""
        severity_weights = {
            "CRITICAL": 25,
            "HIGH": 15,
            "MEDIUM": 5,
            "LOW": 1
        }
        
        score = 0
        for finding in findings:
            severity = finding.get("severity", "LOW")
            score += severity_weights.get(severity, 1)
        
        return min(score, 100)
    
    def _generate_recommendations(self, findings: List[Dict[str, Any]]) -> List[str]:
        """Generate security recommendations based on findings"""
        recommendations = []
        
        categories = set(f["category"] for f in findings)
        
        if "exposed_service" in categories:
            recommendations.append("Restrict access to sensitive services using firewall rules")
        
        if "ssl_expiring" in categories:
            recommendations.append("Renew SSL certificates before expiration")
        
        if "missing_security_headers" in categories:
            recommendations.append("Implement security headers (HSTS, CSP, X-Frame-Options)")
        
        if "dangerous_port" in categories:
            recommendations.append("Close or restrict access to dangerous ports")
        
        return recommendations
    
    async def _ingest_security_report(self, report: Dict[str, Any]):
        """Ingest security analysis report into memory"""
        report_id = self.ingestor._generate_id(f"security_report_{report['timestamp']}")
        
        self.ingestor.memory.upsert_entity(
            entity_id=report_id,
            etype="security_report",
            labels=["SecurityReport"],
            properties={
                "timestamp": report["timestamp"],
                "risk_score": report["risk_score"],
                "total_findings": len(report["findings"]),
                "recommendations": report["recommendations"]
            }
        )
        
        # Store full report in vector database
        doc_id = f"doc_{report_id}"
        report_text = f"""
        Security Analysis Report
        Timestamp: {report['timestamp']}
        Risk Score: {report['risk_score']}/100
        
        Findings: {len(report['findings'])}
        {json.dumps(report['findings'], indent=2)}
        
        Recommendations:
        {chr(10).join('- ' + r for r in report['recommendations'])}
        """
        
        self.ingestor.memory.attach_document(
            entity_id=report_id,
            doc_id=doc_id,
            text=report_text,
            metadata={"type": "security_report"}
        )


class NetworkVisualization:
    """
    Generate network topology visualizations.
    """
    
    def __init__(self, ingestor: NetworkInfrastructureIngestor):
        self.ingestor = ingestor
    
    def generate_graphviz(self, output_file: str = "network_topology.dot"):
        """Generate Graphviz DOT file for network topology"""
        dot_content = ["digraph network {", "  rankdir=LR;", ""]
        
        # Query network topology
        seeds = self.ingestor.memory.graph.list_subgraph_seeds()
        
        # Add nodes
        dot_content.append("  // Nodes")
        for host_ip, host in self.ingestor.discovered_hosts.items():
            node_label = f"{host.hostname or host.ip}\\n{host.ip}"
            color = self._get_node_color(host.node_type)
            dot_content.append(f'  "{host.ip}" [label="{node_label}", shape=box, style=filled, fillcolor="{color}"];')
        
        dot_content.append("\n  // Links")
        # Add edges
        for link in self.ingestor.discovered_links:
            label = f"{link.link_type}"
            if link.port:
                label += f":{link.port}"
            dot_content.append(f'  "{link.source}" -> "{link.target}" [label="{label}"];')
        
        dot_content.append("}")
        
        # Write to file
        with open(output_file, 'w') as f:
            f.write('\n'.join(dot_content))
        
        print(f"Network topology saved to {output_file}")
        print(f"Generate PNG with: dot -Tpng {output_file} -o network_topology.png")
    
    def _get_node_color(self, node_type: str) -> str:
        """Get color for node type"""
        colors = {
            "host": "lightblue",
            "router": "lightgreen",
            "switch": "lightyellow",
            "firewall": "lightcoral",
            "loadbalancer": "lightpink"
        }
        return colors.get(node_type, "lightgray")
    
    def generate_html_map(self, output_file: str = "network_map.html"):
        """Generate interactive HTML network map using D3.js"""
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Network Topology Map</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body { margin: 0; font-family: Arial, sans-serif; }
        #map { width: 100vw; height: 100vh; }
        .node { cursor: pointer; }
        .link { stroke: #999; stroke-opacity: 0.6; }
        .tooltip {
            position: absolute;
            padding: 10px;
            background: rgba(0,0,0,0.8);
            color: white;
            border-radius: 5px;
            pointer-events: none;
            display: none;
        }
    </style>
</head>
<body>
    <div id="map"></div>
    <div class="tooltip" id="tooltip"></div>
    <script>
        const data = %s;
        
        const width = window.innerWidth;
        const height = window.innerHeight;
        
        const svg = d3.select("#map")
            .append("svg")
            .attr("width", width)
            .attr("height", height);
        
        const simulation = d3.forceSimulation(data.nodes)
            .force("link", d3.forceLink(data.links).id(d => d.id).distance(100))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2));
        
        const link = svg.append("g")
            .selectAll("line")
            .data(data.links)
            .enter().append("line")
            .attr("class", "link")
            .attr("stroke-width", 2);
        
        const node = svg.append("g")
            .selectAll("circle")
            .data(data.nodes)
            .enter().append("circle")
            .attr("class", "node")
            .attr("r", 10)
            .attr("fill", d => d.color)
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended))
            .on("mouseover", showTooltip)
            .on("mouseout", hideTooltip);
        
        const tooltip = d3.select("#tooltip");
        
        function showTooltip(event, d) {
            tooltip.style("display", "block")
                .style("left", (event.pageX + 10) + "px")
                .style("top", (event.pageY - 10) + "px")
                .html(`<strong>${d.label}</strong><br>Type: ${d.type}<br>IP: ${d.id}`);
        }
        
        function hideTooltip() {
            tooltip.style("display", "none");
        }
        
        simulation.on("tick", () => {
            link.attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            
            node.attr("cx", d => d.x)
                .attr("cy", d => d.y);
        });
        
        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }
        
        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }
        
        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }
    </script>
</body>
</html>
"""
        
        # Prepare data for D3.js
        nodes = []
        for host_ip, host in self.ingestor.discovered_hosts.items():
            nodes.append({
                "id": host.ip,
                "label": host.hostname or host.ip,
                "type": host.node_type,
                "color": self._get_node_color(host.node_type)
            })
        
        links = []
        for link in self.ingestor.discovered_links:
            links.append({
                "source": link.source,
                "target": link.target,
                "type": link.link_type
            })
        
        network_data = {"nodes": nodes, "links": links}
        
        # Write HTML file
        html_content = html_template % json.dumps(network_data)
        with open(output_file, 'w') as f:
            f.write(html_content)
        
        print(f"Interactive network map saved to {output_file}")
        print(f"Open in browser: file://{os.path.abspath(output_file)}")


# ==================== Integration Examples ====================

async def full_infrastructure_scan():
    """Complete infrastructure discovery example"""
    # from hybrid_memory import HybridMemory
    
    memory = HybridMemory(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
        chroma_dir="./chroma_db"
    )
    
    ingestor = NetworkInfrastructureIngestor(memory)
    scanner = NetworkScanner()
    print("="*60)
    print("COMPREHENSIVE INFRASTRUCTURE DISCOVERY")
    print("="*60)
    
    # 1. Local Network
    print("\n[1/6] Discovering local network...")
    await scanner.discover_local_network(ingestor)

    await ingestor.discover_network_services("192.168.0.200")
    
    await ingestor.scan_network_range("192.168.0.1/24")

    # 2. DNS and Domains
    print("\n[2/6] Discovering DNS records...")
    domains = ["maxhodl.com", "http://boejaker.com"]
    for domain in domains:
        await ingestor.discover_dns_records(domain)
        await ingestor.whois_lookup(domain)
    
    # 3. Websites
    print("\n[3/6] Discovering website structures...")
        # Discover website
    print("\nDiscovering website structure...")
    website = await ingestor.discover_website("https://maxhodl.com", max_depth=2)
    print(f"Found {len(website['pages'])} pages")
    print(f"Technologies: {website['technologies']}")
    
    # 4. Cloud Infrastructure
    print("\n[4/6] Discovering cloud infrastructure...")
    await ingestor.discover_aws_infrastructure()
    await ingestor.discover_kubernetes_cluster()
    
    # Discover Docker containers
    print("\nDiscovering Docker containers...")
    docker = await ingestor.discover_docker_containers()
    if "error" in docker:
        print(f"Error discovering Docker containers: {docker['error']}")
    else:
        print(f"Found {len(docker['containers'])} containers and {len(docker['networks'])} networks")
    
    # 5. Security Analysis
    print("\n[5/6] Running security analysis...")
    security_analyzer = NetworkSecurityAnalyzer(ingestor)
    report = await security_analyzer.analyze_network_security()
    print(f"Security Risk Score: {report['risk_score']}/100")
    print(f"Findings: {len(report['findings'])}")
    
    # 6. Generate Visualizations
    print("\n[6/6] Generating visualizations...")
    visualizer = NetworkVisualization(ingestor)
    visualizer.generate_html_map()
    visualizer.generate_graphviz()
    
    print("\n" + "="*60)
    print("DISCOVERY COMPLETE")
    print("="*60)
    print(f"Total hosts discovered: {len(ingestor.discovered_hosts)}")
    print(ingestor.discovered_hosts)
    print(f"Total links discovered: {len(ingestor.discovered_links)}")
    print(ingestor.discovered_links)
    print(f"Total segments discovered: {len(ingestor.discovered_segments)}")
    print(ingestor.discovered_segments)
    print(f"Total services discovered: {len(ingestor.discovered_services)}")
    print(ingestor.discovered_services)
    print(f"Total websites discovered: {len(ingestor.discovered_websites)}")
    # print(ingestor.discovered_websites)
    print(f"Total web assets discovered: {len(ingestor.discovered_web_assets)}")
    # print(ingestor.discovered_web_assets)
    print(f"Total cloud resources discovered: {len(ingestor.discovered_cloud_resources)}")
    print(ingestor.discovered_cloud_resources)

if __name__ == "__main__":
    import os
    asyncio.run(full_infrastructure_scan())