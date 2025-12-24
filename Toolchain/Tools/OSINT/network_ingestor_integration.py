#!/usr/bin/env python3
"""
Network Infrastructure Scanner Integration - IMPROVED VERSION

Changes:
- Enhanced vector store integration for all scan results
- Streamlined output (concise summaries instead of verbose listings)
- Better knowledge graph integration
- All results semantically searchable
- Removed unnecessary verbosity

Wraps the comprehensive network infrastructure ingestor as OSINT tools
with proper memory integration and tool schema validation.
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain.tools import StructuredTool
import logging

logger = logging.getLogger(__name__)

# Import the user's scanner
try:
    from Vera.Memory.network_ingestor import (
        NetworkInfrastructureIngestor,
        NetworkScanner,
        NetworkNode,
        NetworkSegment,
        WebAsset,
        CloudResource
    )
    SCANNER_AVAILABLE = True
except ImportError:
    try:
        from Memory.network_ingestor import (
            NetworkInfrastructureIngestor,
            NetworkScanner,
            NetworkNode,
            NetworkSegment,
            WebAsset,
            CloudResource
        )
        SCANNER_AVAILABLE = True
    except ImportError:
        SCANNER_AVAILABLE = False
        logger.warning("Network infrastructure scanner not available")


# =============================================================================
# PYDANTIC SCHEMAS FOR TOOL INPUTS
# =============================================================================

class LocalNetworkDiscoveryInput(BaseModel):
    """Schema for local network discovery"""
    interface: Optional[str] = Field(default=None, description="Network interface to scan (default: auto-detect)")
    timeout: int = Field(default=3, description="Timeout for host detection in seconds")

class NetworkRangeScanInput(BaseModel):
    """Schema for network range scanning"""
    cidr: str = Field(..., description="Network CIDR (e.g., '192.168.1.0/24')")
    scan_type: str = Field(default="ping", description="Scan type: 'ping', 'syn', or 'comprehensive'")

class WebsiteCrawlInput(BaseModel):
    """Schema for website discovery"""
    url: str = Field(..., description="Website URL to crawl")
    max_depth: int = Field(default=2, description="Maximum crawl depth (0-5)")
    max_pages: int = Field(default=100, description="Maximum pages to crawl")

class DNSDiscoveryInput(BaseModel):
    """Schema for DNS record discovery"""
    domain: str = Field(..., description="Domain to enumerate")
    include_subdomains: bool = Field(default=True, description="Perform subdomain enumeration")

class ServiceDiscoveryInput(BaseModel):
    """Schema for service discovery"""
    target: str = Field(..., description="IP address or hostname to scan")
    port_range: str = Field(default="1-1000", description="Port range to scan (e.g., '1-1000', '80,443,8080')")

class TraceRouteInput(BaseModel):
    """Schema for traceroute"""
    target: str = Field(..., description="Target IP or hostname")
    max_hops: int = Field(default=30, description="Maximum hops to trace")

class WHOISLookupInput(BaseModel):
    """Schema for WHOIS lookup"""
    domain: str = Field(..., description="Domain for WHOIS lookup")

class SSLScanInput(BaseModel):
    """Schema for SSL certificate scanning"""
    hostname: str = Field(..., description="Hostname to scan")
    port: int = Field(default=443, description="SSL port (default 443)")

class CloudInfraInput(BaseModel):
    """Schema for cloud infrastructure discovery"""
    provider: str = Field(..., description="Cloud provider: 'aws', 'azure', 'gcp', 'kubernetes', 'docker'")
    region: Optional[str] = Field(default=None, description="Region for AWS/Azure/GCP (optional)")
    project_id: Optional[str] = Field(default=None, description="Project ID for GCP (optional)")
    subscription_id: Optional[str] = Field(default=None, description="Subscription ID for Azure (optional)")
    context: Optional[str] = Field(default=None, description="Context for Kubernetes (optional)")


# =============================================================================
# NETWORK INFRASTRUCTURE SCANNER WRAPPER - IMPROVED
# =============================================================================

class NetworkInfrastructureTools:
    """Wrapper for comprehensive network infrastructure scanner with full memory integration"""
    
    def __init__(self, agent):
        self.agent = agent
        
        if not SCANNER_AVAILABLE:
            logger.error("Network infrastructure scanner not available")
            return
        
        # Initialize the ingestor with agent's memory
        self.ingestor = NetworkInfrastructureIngestor(
            memory=agent.mem,
            credentials={}  # Can be configured via env vars
        )
        
        self.network_scanner = NetworkScanner()
        
        logger.info("Network infrastructure scanner initialized with full memory integration")
    
    def _add_to_vector_store(self, doc_id: str, text: str, metadata: Dict[str, Any]):
        """Add document to vector store for semantic search"""
        try:
            self.agent.mem.vec.add_texts(
                "long_term_docs",
                [doc_id],
                [text],
                [metadata]
            )
            logger.debug(f"Added {doc_id} to vector store")
        except Exception as e:
            logger.error(f"Failed to add to vector store: {e}")
    
    # -------------------------------------------------------------------------
    # LOCAL NETWORK DISCOVERY
    # -------------------------------------------------------------------------
    
    def discover_local_network(self, interface: Optional[str] = None, timeout: int = 3) -> str:
        """
        Discover devices on local network.
        
        Performs host discovery on the local network segment using:
        - Nmap ping scan (if available and running as root)
        - TCP connect scan (fallback for unprivileged users)
        
        All discovered hosts are automatically stored in Neo4j graph
        and ChromaDB vector store with relationships showing network topology.
        
        Args:
            interface: Network interface (auto-detected if not specified)
            timeout: Timeout for host detection
        
        Returns:
            Concise summary of discovered hosts and network segments
        """
        if not SCANNER_AVAILABLE:
            return "[Error] Network scanner not available"
        
        try:
            # Run async discovery
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                self.network_scanner.discover_local_network(
                    self.ingestor,
                    interface=interface,
                    timeout=timeout
                )
            )
            
            if "error" in result:
                return f"[Error] {result['error']}"
            
            hosts = result.get('hosts', [])
            network = result.get('network', 'Unknown')
            segments = result.get('segments', [])
            
            # Store summary in vector store
            import time
            scan_id = f"local_net_scan_{int(time.time()*1000)}"
            summary = f"Local network discovery on {network}: {len(hosts)} active hosts found"
            if segments:
                summary += f", {len(segments)} network segments identified"
            
            self._add_to_vector_store(
                doc_id=scan_id,
                text=summary,
                metadata={
                    "type": "local_network_discovery",
                    "network": network,
                    "host_count": len(hosts),
                    "segment_count": len(segments),
                    "timestamp": time.time()
                }
            )
            
            # Generate concise output
            output = [f"✅ Local Network Discovery Complete"]
            output.append(f"Network: {network}")
            output.append(f"Active Hosts: {len(hosts)}")
            
            if segments:
                output.append(f"Network Segments: {len(segments)}")
            
            if hosts:
                output.append(f"\nTop Hosts:")
                for host in hosts[:5]:
                    hostname = host.hostname or "Unknown"
                    output.append(f"  • {host.ip} ({hostname})")
                if len(hosts) > 5:
                    output.append(f"  ... and {len(hosts) - 5} more hosts")
            
            output.append(f"\n💾 All hosts stored in knowledge graph (search: 'local network hosts')")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Local network discovery failed: {e}", exc_info=True)
            return f"[Error] Discovery failed: {str(e)}"
    
    # -------------------------------------------------------------------------
    # NETWORK RANGE SCANNING
    # -------------------------------------------------------------------------
    
    def scan_network_range(self, cidr: str, scan_type: str = "ping") -> str:
        """
        Scan a network range for active hosts.
        
        Scan types:
        - 'ping': ICMP ping scan (fast, requires root)
        - 'syn': SYN scan (stealthy, requires root)
        - 'comprehensive': Full scan with OS detection (slow, requires root)
        
        Results stored in graph and vector store with full semantic search capability.
        
        Args:
            cidr: Network in CIDR notation (e.g., "192.168.1.0/24")
            scan_type: Type of scan to perform
        
        Returns:
            Concise summary of discovered hosts
        """
        if not SCANNER_AVAILABLE:
            return "[Error] Network scanner not available"
        
        try:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                self.ingestor.scan_network_range(cidr, scan_type=scan_type)
            )
            
            if "error" in result:
                return f"[Error] {result['error']}"
            
            total_scanned = result.get('total_scanned', 0)
            total_alive = result.get('total_alive', 0)
            hosts = result.get('hosts', [])
            
            # Store in vector store
            import time
            scan_id = f"range_scan_{int(time.time()*1000)}"
            summary = f"Network range scan {cidr} ({scan_type}): {total_alive} of {total_scanned} hosts alive"
            
            self._add_to_vector_store(
                doc_id=scan_id,
                text=summary,
                metadata={
                    "type": "network_range_scan",
                    "cidr": cidr,
                    "scan_type": scan_type,
                    "total_scanned": total_scanned,
                    "total_alive": total_alive,
                    "timestamp": time.time()
                }
            )
            
            # Generate concise output
            output = [f"✅ Network Range Scan Complete"]
            output.append(f"Range: {cidr} | Type: {scan_type}")
            output.append(f"Scanned: {total_scanned} | Alive: {total_alive}")
            
            if hosts:
                output.append(f"\nTop Hosts:")
                for host in hosts[:5]:
                    hostname = host.hostname or "No hostname"
                    os_info = f" - {host.os}" if host.os else ""
                    output.append(f"  • {host.ip} ({hostname}){os_info}")
                if len(hosts) > 5:
                    output.append(f"  ... and {len(hosts) - 5} more hosts")
            
            output.append(f"\n💾 Results stored in knowledge graph (search: 'scan {cidr}')")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Network range scan failed: {e}", exc_info=True)
            return f"[Error] Scan failed: {str(e)}"
    
    # -------------------------------------------------------------------------
    # SERVICE DISCOVERY
    # -------------------------------------------------------------------------
    
    def discover_services(self, target: str, port_range: str = "1-1000") -> str:
        """
        Discover services running on a host.
        
        Performs detailed service detection including:
        - Port scanning
        - Service fingerprinting
        - Version detection
        - Banner grabbing
        - Script execution (banner, ssl-cert)
        
        Results stored with service-to-host relationships in graph and vector store.
        
        Args:
            target: IP address or hostname
            port_range: Ports to scan (e.g., "1-1000", "80,443,8080")
        
        Returns:
            Concise service information summary
        """
        if not SCANNER_AVAILABLE:
            return "[Error] Network scanner not available"
        
        try:
            loop = asyncio.get_event_loop()
            host = loop.run_until_complete(
                self.ingestor.discover_network_services(target, port_range=port_range)
            )
            
            services = host.services
            
            # Store in vector store
            import time
            scan_id = f"service_disc_{int(time.time()*1000)}"
            summary = f"Service discovery on {target}: {len(services)} services detected"
            if services:
                service_list = ", ".join([f"{s.get('service', 'unknown')}:{s.get('port')}" for s in services[:5]])
                summary += f". Services: {service_list}"
            
            self._add_to_vector_store(
                doc_id=scan_id,
                text=summary,
                metadata={
                    "type": "service_discovery",
                    "target": target,
                    "service_count": len(services),
                    "port_range": port_range,
                    "timestamp": time.time()
                }
            )
            
            # Generate concise output
            output = [f"✅ Service Discovery Complete"]
            output.append(f"Target: {target}")
            if host.hostname:
                output.append(f"Hostname: {host.hostname}")
            output.append(f"Services: {len(services)}")
            
            if services:
                output.append(f"\nKey Services:")
                for svc in services[:5]:
                    product = svc.get('product', '')
                    version = svc.get('version', '')
                    prod_info = f" - {product} {version}" if product else ""
                    output.append(f"  • Port {svc.get('port')}: {svc.get('service', 'unknown')}{prod_info}")
                if len(services) > 5:
                    output.append(f"  ... and {len(services) - 5} more services")
            
            output.append(f"\n💾 Services stored with host relationships (search: 'services {target}')")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Service discovery failed: {e}", exc_info=True)
            return f"[Error] Discovery failed: {str(e)}"
    
    # -------------------------------------------------------------------------
    # WEBSITE CRAWLING
    # -------------------------------------------------------------------------
    
    def crawl_website(self, url: str, max_depth: int = 2, max_pages: int = 100) -> str:
        """
        Discover and map website structure.
        
        Crawls website to discover:
        - Pages and their relationships
        - External resources (scripts, images, CSS)
        - Forms and input fields
        - Technologies used
        - Security headers
        
        Creates comprehensive graph structure:
        Website → Pages → Assets with proper parent-child relationships.
        All results semantically searchable.
        
        Args:
            url: Website URL to crawl
            max_depth: Maximum crawl depth (0-5)
            max_pages: Maximum pages to crawl
        
        Returns:
            Concise website structure summary
        """
        if not SCANNER_AVAILABLE:
            return "[Error] Network scanner not available"
        
        try:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                self.ingestor.discover_website(url, max_depth=max_depth, max_pages=max_pages)
            )
            
            pages = result.get('pages', [])
            assets = result.get('assets', [])
            forms = result.get('forms', [])
            technologies = result.get('technologies', [])
            
            # Store in vector store
            import time
            scan_id = f"web_crawl_{int(time.time()*1000)}"
            summary = f"Website crawl of {url}: {len(pages)} pages, {len(assets)} assets"
            if technologies:
                tech_list = ", ".join(technologies[:5])
                summary += f". Technologies: {tech_list}"
            
            self._add_to_vector_store(
                doc_id=scan_id,
                text=summary,
                metadata={
                    "type": "website_crawl",
                    "url": url,
                    "page_count": len(pages),
                    "asset_count": len(assets),
                    "form_count": len(forms),
                    "timestamp": time.time()
                }
            )
            
            # Generate concise output
            output = [f"✅ Website Discovery Complete"]
            output.append(f"URL: {url}")
            output.append(f"Pages: {len(pages)} | Assets: {len(assets)} | Forms: {len(forms)}")
            
            if technologies:
                output.append(f"\nTechnologies ({len(technologies)}):")
                for tech in technologies[:5]:
                    output.append(f"  • {tech}")
                if len(technologies) > 5:
                    output.append(f"  ... and {len(technologies) - 5} more")
            
            if forms:
                output.append(f"\nForms: {len(forms)} detected")
            
            output.append(f"\n💾 Website structure stored in graph (search: 'website {url}')")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Website crawl failed: {e}", exc_info=True)
            return f"[Error] Crawl failed: {str(e)}"
    
    # -------------------------------------------------------------------------
    # DNS DISCOVERY
    # -------------------------------------------------------------------------
    
    def discover_dns(self, domain: str, include_subdomains: bool = True) -> str:
        """
        Comprehensive DNS reconnaissance.
        
        Discovers:
        - A, AAAA, MX, NS, TXT, SOA records
        - Subdomains (via brute force)
        - WHOIS information
        
        All DNS data stored in graph with domain as central node.
        Results semantically searchable.
        
        Args:
            domain: Domain to enumerate
            include_subdomains: Perform subdomain enumeration
        
        Returns:
            Concise DNS information summary
        """
        if not SCANNER_AVAILABLE:
            return "[Error] Network scanner not available"
        
        try:
            loop = asyncio.get_event_loop()
            
            # DNS records
            dns_records = loop.run_until_complete(
                self.ingestor.discover_dns_records(domain)
            )
            
            # WHOIS
            whois_data = loop.run_until_complete(
                self.ingestor.whois_lookup(domain)
            )
            
            # Subdomains
            subdomains = []
            if include_subdomains:
                subdomains = loop.run_until_complete(
                    self.ingestor.discover_subdomains(domain)
                )
            
            # Store in vector store
            import time
            scan_id = f"dns_disc_{int(time.time()*1000)}"
            summary = f"DNS discovery for {domain}: "
            summary += f"{len(dns_records.get('A', []))} A records, "
            summary += f"{len(dns_records.get('NS', []))} nameservers"
            if subdomains:
                summary += f", {len(subdomains)} subdomains"
            if whois_data.get('registrar'):
                summary += f". Registrar: {whois_data['registrar']}"
            
            self._add_to_vector_store(
                doc_id=scan_id,
                text=summary,
                metadata={
                    "type": "dns_discovery",
                    "domain": domain,
                    "subdomain_count": len(subdomains),
                    "registrar": whois_data.get('registrar'),
                    "timestamp": time.time()
                }
            )
            
            # Generate concise output
            output = [f"✅ DNS Discovery Complete"]
            output.append(f"Domain: {domain}")
            
            if dns_records.get('A'):
                output.append(f"A Records: {len(dns_records['A'])}")
            
            if dns_records.get('NS'):
                output.append(f"Nameservers: {len(dns_records['NS'])}")
            
            if dns_records.get('MX'):
                output.append(f"MX Records: {len(dns_records['MX'])}")
            
            if whois_data.get('registrar'):
                output.append(f"Registrar: {whois_data['registrar']}")
            
            if subdomains:
                output.append(f"\n🔍 Subdomains: {len(subdomains)} discovered")
                for sub in subdomains[:5]:
                    output.append(f"  • {sub}")
                if len(subdomains) > 5:
                    output.append(f"  ... and {len(subdomains) - 5} more")
            
            output.append(f"\n💾 DNS data stored in graph (search: 'DNS {domain}')")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"DNS discovery failed: {e}", exc_info=True)
            return f"[Error] Discovery failed: {str(e)}"
    
    # -------------------------------------------------------------------------
    # TRACEROUTE
    # -------------------------------------------------------------------------
    
    def trace_route(self, target: str, max_hops: int = 30) -> str:
        """
        Trace network route to target.
        
        Discovers intermediate hops (routers) between local host and target.
        Creates graph relationships showing network path.
        Results stored in vector store for search.
        
        Requires root/admin privileges for ICMP.
        
        Args:
            target: Target IP or hostname
            max_hops: Maximum hops to trace
        
        Returns:
            Concise route information
        """
        if not SCANNER_AVAILABLE:
            return "[Error] Network scanner not available"
        
        try:
            loop = asyncio.get_event_loop()
            route = loop.run_until_complete(
                self.ingestor.trace_route(target, max_hops=max_hops)
            )
            
            # Store in vector store
            import time
            scan_id = f"traceroute_{int(time.time()*1000)}"
            summary = f"Traceroute to {target}: {len(route)} hops"
            if route:
                first_hop = route[0].ip
                last_hop = route[-1].ip
                summary += f" from {first_hop} to {last_hop}"
            
            self._add_to_vector_store(
                doc_id=scan_id,
                text=summary,
                metadata={
                    "type": "traceroute",
                    "target": target,
                    "hop_count": len(route),
                    "timestamp": time.time()
                }
            )
            
            # Generate concise output
            output = [f"✅ Traceroute Complete"]
            output.append(f"Target: {target}")
            output.append(f"Hops: {len(route)}")
            
            if route:
                output.append(f"\nKey Hops:")
                for i, hop in enumerate([route[0]] + route[-3:] if len(route) > 4 else route, 1):
                    hostname = hop.hostname or "Unknown"
                    rtt = hop.metadata.get('rtt', 0) if hop.metadata else 0
                    output.append(f"  {i}. {hop.ip} ({hostname}) - {rtt:.2f}ms")
                if len(route) > 4:
                    output.append(f"  ... {len(route) - 4} intermediate hops")
            
            output.append(f"\n💾 Route stored with hop relationships (search: 'route to {target}')")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Traceroute failed: {e}", exc_info=True)
            return f"[Error] Traceroute failed: {str(e)}"
    
    # -------------------------------------------------------------------------
    # SSL CERTIFICATE SCANNING
    # -------------------------------------------------------------------------
    
    def scan_ssl_certificate(self, hostname: str, port: int = 443) -> str:
        """
        Scan SSL/TLS certificate.
        
        Extracts certificate information:
        - Issuer and subject
        - Validity dates
        - Serial number
        - Subject Alternative Names (SAN)
        
        Results stored in graph and vector store.
        
        Args:
            hostname: Target hostname
            port: SSL port (default 443)
        
        Returns:
            Concise certificate information
        """
        if not SCANNER_AVAILABLE:
            return "[Error] Network scanner not available"
        
        try:
            loop = asyncio.get_event_loop()
            cert_info = loop.run_until_complete(
                self.ingestor.scan_ssl_certificate(hostname, port=port)
            )
            
            if "error" in cert_info:
                return f"[Error] {cert_info['error']}"
            
            # Store in vector store
            import time
            scan_id = f"ssl_scan_{int(time.time()*1000)}"
            issuer = cert_info.get('issuer', {})
            issuer_name = issuer.get('organizationName', issuer.get('commonName', 'Unknown'))
            summary = f"SSL certificate for {hostname}:{port}. Issued by {issuer_name}"
            if cert_info.get('valid'):
                summary += ". Certificate valid"
            else:
                summary += ". Certificate INVALID"
            
            self._add_to_vector_store(
                doc_id=scan_id,
                text=summary,
                metadata={
                    "type": "ssl_scan",
                    "hostname": hostname,
                    "port": port,
                    "valid": cert_info.get('valid', False),
                    "issuer": issuer_name,
                    "timestamp": time.time()
                }
            )
            
            # Generate concise output
            output = [f"✅ SSL Certificate Scan Complete"]
            output.append(f"Target: {hostname}:{port}")
            
            if cert_info.get('valid'):
                issuer = cert_info.get('issuer', {})
                subject = cert_info.get('subject', {})
                
                output.append(f"\n📜 Certificate Valid ✓")
                output.append(f"Issuer: {issuer.get('organizationName', issuer.get('commonName', 'Unknown'))}")
                output.append(f"Subject: {subject.get('commonName', 'Unknown')}")
                output.append(f"Valid Until: {cert_info.get('not_after', 'Unknown')}")
                
                san = cert_info.get('san', [])
                if san:
                    output.append(f"SANs: {len(san)} alternate names")
            else:
                output.append(f"\n❌ Certificate INVALID")
            
            output.append(f"\n💾 Certificate data stored in graph (search: 'SSL cert {hostname}')")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"SSL scan failed: {e}", exc_info=True)
            return f"[Error] Scan failed: {str(e)}"
    
    # -------------------------------------------------------------------------
    # CLOUD INFRASTRUCTURE DISCOVERY
    # -------------------------------------------------------------------------
    
    def discover_cloud_infrastructure(self, provider: str, region: Optional[str] = None,
                                    project_id: Optional[str] = None,
                                    subscription_id: Optional[str] = None,
                                    context: Optional[str] = None) -> str:
        """
        Discover cloud infrastructure resources.
        
        Supported providers:
        - aws: EC2, VPC, RDS, ELB, S3 (requires AWS credentials)
        - azure: VNets, VMs, Databases (requires Azure credentials)
        - gcp: Compute Engine, Networks (requires GCP credentials)
        - kubernetes: Pods, Services, Deployments, Ingresses
        - docker: Containers, Networks, Images, Volumes
        
        Credentials should be configured via environment variables.
        All resources stored in graph and vector store.
        
        Args:
            provider: Cloud provider
            region: AWS/Azure/GCP region
            project_id: GCP project ID
            subscription_id: Azure subscription ID
            context: Kubernetes context
        
        Returns:
            Concise summary of discovered cloud resources
        """
        if not SCANNER_AVAILABLE:
            return "[Error] Network scanner not available"
        
        try:
            loop = asyncio.get_event_loop()
            
            provider = provider.lower()
            
            if provider == "aws":
                region = region or "us-east-1"
                result = loop.run_until_complete(
                    self.ingestor.discover_aws_infrastructure(region=region)
                )
            elif provider == "azure":
                if not subscription_id:
                    return "[Error] Azure requires subscription_id parameter"
                result = loop.run_until_complete(
                    self.ingestor.discover_azure_infrastructure(subscription_id=subscription_id)
                )
            elif provider == "gcp":
                if not project_id:
                    return "[Error] GCP requires project_id parameter"
                result = loop.run_until_complete(
                    self.ingestor.discover_gcp_infrastructure(project_id=project_id)
                )
            elif provider == "kubernetes" or provider == "k8s":
                result = loop.run_until_complete(
                    self.ingestor.discover_kubernetes_cluster(context_name=context)
                )
            elif provider == "docker":
                result = loop.run_until_complete(
                    self.ingestor.discover_docker_containers()
                )
            else:
                return f"[Error] Unsupported provider: {provider}"
            
            if "error" in result:
                return f"[Error] {result['error']}"
            
            # Store in vector store
            import time
            scan_id = f"cloud_{provider}_{int(time.time()*1000)}"
            summary = f"Cloud infrastructure discovery for {provider.upper()}"
            if provider == "aws":
                summary += f": {len(result.get('ec2_instances', []))} EC2, {len(result.get('vpcs', []))} VPCs"
            elif provider in ["kubernetes", "k8s"]:
                summary += f": {len(result.get('pods', []))} pods, {len(result.get('services', []))} services"
            elif provider == "docker":
                summary += f": {len(result.get('containers', []))} containers, {len(result.get('images', []))} images"
            
            self._add_to_vector_store(
                doc_id=scan_id,
                text=summary,
                metadata={
                    "type": "cloud_discovery",
                    "provider": provider,
                    "region": region,
                    "timestamp": time.time()
                }
            )
            
            # Generate concise output
            output = [f"✅ Cloud Infrastructure Discovery Complete"]
            output.append(f"Provider: {provider.upper()}")
            
            if provider == "aws":
                output.append(f"Region: {region}")
                output.append(f"VPCs: {len(result.get('vpcs', []))}")
                output.append(f"EC2 Instances: {len(result.get('ec2_instances', []))}")
                output.append(f"RDS Instances: {len(result.get('rds_instances', []))}")
                output.append(f"Load Balancers: {len(result.get('load_balancers', []))}")
                output.append(f"S3 Buckets: {len(result.get('s3_buckets', []))}")
            
            elif provider in ["kubernetes", "k8s"]:
                output.append(f"Namespaces: {len(result.get('namespaces', []))}")
                output.append(f"Pods: {len(result.get('pods', []))}")
                output.append(f"Services: {len(result.get('services', []))}")
                output.append(f"Deployments: {len(result.get('deployments', []))}")
                output.append(f"Ingresses: {len(result.get('ingresses', []))}")
            
            elif provider == "docker":
                output.append(f"Containers: {len(result.get('containers', []))}")
                output.append(f"Images: {len(result.get('images', []))}")
                output.append(f"Networks: {len(result.get('networks', []))}")
                output.append(f"Volumes: {len(result.get('volumes', []))}")
            
            output.append(f"\n💾 Cloud resources stored in graph (search: '{provider} infrastructure')")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.error(f"Cloud discovery failed: {e}", exc_info=True)
            return f"[Error] Discovery failed: {str(e)}"


# =============================================================================
# TOOL LOADER INTEGRATION
# =============================================================================

def add_network_infrastructure_tools(tool_list: List, agent):
    """
    Add comprehensive network infrastructure scanner tools - IMPROVED VERSION
    
    Changes:
    - Enhanced vector store integration for all results
    - Streamlined output (concise summaries)
    - Full semantic search capability
    - Better knowledge graph integration
    """
    
    if not SCANNER_AVAILABLE:
        logger.warning("Network infrastructure scanner not available - skipping tools")
        return tool_list
    
    infra_tools = NetworkInfrastructureTools(agent)
    
    tool_list.extend([
        StructuredTool.from_function(
            func=infra_tools.discover_local_network,
            name="discover_local_network",
            description=(
                "Discover all devices on the local network segment. "
                "Uses nmap (if available) or TCP connect scan fallback. "
                "Automatically maps network topology in graph memory. All results semantically searchable."
            ),
            args_schema=LocalNetworkDiscoveryInput
        ),
        
        StructuredTool.from_function(
            func=infra_tools.scan_network_range,
            name="scan_network_range",
            description=(
                "Scan a network range in CIDR notation for active hosts. "
                "Supports ping, SYN, and comprehensive scans with OS detection. "
                "All discovered hosts stored in knowledge graph and vector store."
            ),
            args_schema=NetworkRangeScanInput
        ),
        
        StructuredTool.from_function(
            func=infra_tools.discover_services,
            name="discover_network_services",
            description=(
                "Detailed service detection and fingerprinting on a target host. "
                "Identifies service versions, products, and creates service-to-host relationships. "
                "Results fully searchable in knowledge graph."
            ),
            args_schema=ServiceDiscoveryInput
        ),
        
        StructuredTool.from_function(
            func=infra_tools.crawl_website,
            name="crawl_website_structure",
            description=(
                "Comprehensive website crawling and structure discovery. "
                "Maps pages, assets, forms, and technologies with full parent-child relationships. "
                "Includes technology detection and security header analysis. All results searchable."
            ),
            args_schema=WebsiteCrawlInput
        ),
        
        StructuredTool.from_function(
            func=infra_tools.discover_dns,
            name="discover_dns_records",
            description=(
                "DNS reconnaissance with A, MX, NS, TXT, SOA records plus subdomain enumeration. "
                "Includes WHOIS lookup and stores all DNS data in graph memory with semantic search."
            ),
            args_schema=DNSDiscoveryInput
        ),
        
        StructuredTool.from_function(
            func=infra_tools.trace_route,
            name="trace_network_route",
            description=(
                "Trace network path to target showing intermediate hops (routers). "
                "Creates graph relationships showing network topology. Results searchable. Requires root for ICMP."
            ),
            args_schema=TraceRouteInput
        ),
        
        StructuredTool.from_function(
            func=infra_tools.scan_ssl_certificate,
            name="scan_ssl_cert",
            description=(
                "Scan SSL/TLS certificate for a hostname. "
                "Extracts issuer, subject, validity dates, and SANs. Stores in graph memory with semantic search."
            ),
            args_schema=SSLScanInput
        ),
        
        StructuredTool.from_function(
            func=infra_tools.discover_cloud_infrastructure,
            name="discover_cloud_infra",
            description=(
                "Discover cloud infrastructure resources. "
                "Supports AWS, Azure, GCP, Kubernetes, and Docker. "
                "Requires appropriate credentials via environment variables. "
                "All resources stored in graph with cloud provider relationships and semantic search."
            ),
            args_schema=CloudInfraInput
        ),
    ])
    
    logger.info(f"Added {8} network infrastructure scanner tools (improved version)")
    
    return tool_list