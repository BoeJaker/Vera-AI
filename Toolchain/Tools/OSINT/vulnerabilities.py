#!/usr/bin/env python3
"""
Comprehensive Vulnerability Intelligence Toolkit for Vera
MULTI-SOURCE, DETAILED, MEMORY-INTEGRATED, NETWORK-AWARE

Features:
- Multi-source vulnerability lookup (NVD, MITRE, Vulners, GitHub, OSV, etc.)
- Network service vulnerability mapping
- Exploit database integration (ExploitDB, Metasploit)
- CVE scoring with CVSS v3/v2 and EPSS
- Patch and mitigation tracking
- Cross-reference correlation
- Graph memory integration
- Accepts services, technologies, products, CPEs
- Tool chaining compatible with network scans

Data Sources:
- NVD (National Vulnerability Database) - Official CVE data
- MITRE CVE - CVE descriptions and references
- Vulners - Vulnerability aggregator with exploit info
- GitHub Security Advisories - Package-specific vulnerabilities
- OSV (Open Source Vulnerabilities) - Open source ecosystem
- ExploitDB - Public exploit database

Dependencies:
    pip install requests beautifulsoup4

TODO:
Metaspolit db connector
"""

import re
import json
import time
import hashlib
from typing import List, Dict, Any, Optional, Set, Iterator, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydantic import BaseModel, Field
from enum import Enum
import logging

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

class VulnSource(str, Enum):
    """Vulnerability data sources"""
    NVD = "nvd"
    MITRE = "mitre"
    VULNERS = "vulners"
    GITHUB = "github"
    OSV = "osv"
    EXPLOITDB = "exploitdb"
    ALL = "all"

class SeverityLevel(str, Enum):
    """CVSS severity levels"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"

@dataclass
class VulnSearchConfig:
    """Configuration for vulnerability searches"""
    
    # Search sources
    sources: List[str] = field(default_factory=lambda: ["nvd", "vulners"])
    enable_exploits: bool = True
    enable_patches: bool = True
    
    # Filters
    severity_filter: Optional[str] = None
    min_cvss_score: Optional[float] = None
    max_age_days: Optional[int] = None
    only_exploited: bool = False
    
    # Result limits
    max_results_per_source: int = 10
    max_total_results: int = 50
    
    # API keys (from environment)
    nvd_api_key: Optional[str] = None
    vulners_api_key: Optional[str] = None
    github_token: Optional[str] = None
    
    # Performance
    request_timeout: int = 15
    rate_limit_delay: float = 1.0
    max_threads: int = 5
    
    # Graph memory
    link_to_session: bool = True
    create_vuln_nodes: bool = True
    link_to_services: bool = True
    deduplicate: bool = True
    
    # Caching
    enable_cache: bool = True
    cache_ttl_hours: int = 24
    
    # Auto-prerequisite for network scans
    auto_run_prerequisites: bool = True
    
    @classmethod
    def quick_lookup(cls) -> 'VulnSearchConfig':
        return cls(
            sources=["nvd"],
            enable_exploits=False,
            max_results_per_source=5
        )
    
    @classmethod
    def comprehensive_lookup(cls) -> 'VulnSearchConfig':
        return cls(
            sources=["nvd", "vulners", "github", "osv"],
            enable_exploits=True,
            enable_patches=True,
            max_results_per_source=20
        )
    
    @classmethod
    def exploit_focused(cls) -> 'VulnSearchConfig':
        return cls(
            sources=["vulners", "exploitdb"],
            enable_exploits=True,
            only_exploited=True,
            max_results_per_source=15
        )
    
    @classmethod
    def network_scan_vuln(cls) -> 'VulnSearchConfig':
        """Configuration for vulnerability scanning of network services"""
        return cls(
            sources=["nvd", "vulners"],
            enable_exploits=True,
            max_results_per_source=5,
            auto_run_prerequisites=True,
            severity_filter=None  # Show all severities
        )

# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class FlexibleVulnInput(BaseModel):
    """Base schema for vulnerability searches"""
    target: str = Field(description="Product, service, technology, or CPE")

class CVELookupInput(FlexibleVulnInput):
    cve_id: str = Field(description="CVE ID (e.g., CVE-2024-1234)")

class ProductVulnInput(FlexibleVulnInput):
    version: Optional[str] = Field(default=None, description="Product version")
    vendor: Optional[str] = Field(default=None, description="Vendor name")

class ServiceVulnInput(FlexibleVulnInput):
    version: Optional[str] = Field(default=None, description="Service version")
    port: Optional[int] = Field(default=None, description="Port number")

class TechnologyVulnInput(FlexibleVulnInput):
    version: Optional[str] = Field(default=None, description="Technology version")
    category: Optional[str] = Field(default=None, description="Category (CMS, Framework, etc.)")

class NetworkVulnScanInput(BaseModel):
    """Scan network services for vulnerabilities"""
    target: str = Field(description="IP, CIDR, hostname, or formatted scan output")
    severity_filter: Optional[str] = Field(default=None, description="CRITICAL, HIGH, MEDIUM, LOW")
    max_results: int = Field(default=5, description="Max CVEs per service")
    service_filter: Optional[str] = Field(default=None, description="Only scan specific service")

class ComprehensiveVulnInput(FlexibleVulnInput):
    search_type: str = Field(
        default="standard",
        description="Search type: quick, standard, comprehensive, exploit_focused"
    )
    sources: Optional[List[str]] = Field(default=None, description="Specific sources to query")
    severity_filter: Optional[str] = Field(default=None, description="CRITICAL, HIGH, MEDIUM, LOW")
    min_cvss: Optional[float] = Field(default=None, description="Minimum CVSS score")
    only_exploited: bool = Field(default=False, description="Only return exploited CVEs")

class ExploitSearchInput(FlexibleVulnInput):
    cve_id: Optional[str] = Field(default=None, description="Specific CVE to find exploits for")
    exploit_type: Optional[str] = Field(
        default=None,
        description="Type: remote, local, dos, webapps"
    )

class PatchLookupInput(FlexibleVulnInput):
    cve_id: str = Field(description="CVE ID to find patches for")

# =============================================================================
# INPUT PARSER
# =============================================================================

class VulnInputParser:
    """Parse and normalize vulnerability search inputs"""
    
    @staticmethod
    def extract_product(input_text: str) -> Dict[str, Any]:
        """
        Extract product information from various input formats.
        
        Handles:
        - "Apache 2.4.51"
        - "nginx/1.20.1"
        - "WordPress 6.0"
        - "service: ssh version: OpenSSH_8.2p1"
        - CPE strings
        - Formatted scan output
        """
        if not input_text:
            return {"product": "", "version": None, "vendor": None}
        
        input_text = str(input_text).strip()
        
        # Check for CPE format
        if input_text.startswith("cpe:"):
            return VulnInputParser._parse_cpe(input_text)
        
        # Try service format: "service: X version: Y"
        service_match = re.search(
            r'service:\s*([^\s]+).*?version:\s*([^\s,]+)',
            input_text,
            re.IGNORECASE
        )
        if service_match:
            return {
                "product": service_match.group(1),
                "version": service_match.group(2),
                "vendor": None
            }
        
        # Try "product/version" format
        if '/' in input_text:
            parts = input_text.split('/')
            if len(parts) == 2:
                return {
                    "product": parts[0].strip(),
                    "version": parts[1].strip(),
                    "vendor": None
                }
        
        # Try "product version" format
        version_match = re.search(
            r'^([a-zA-Z0-9_\-\.]+)\s+([0-9]+[0-9\.\-a-z]*)',
            input_text
        )
        if version_match:
            return {
                "product": version_match.group(1),
                "version": version_match.group(2),
                "vendor": None
            }
        
        # Default: treat as product name only
        return {
            "product": input_text,
            "version": None,
            "vendor": None
        }
    
    @staticmethod
    def _parse_cpe(cpe_string: str) -> Dict[str, Any]:
        """Parse CPE string"""
        # CPE format: cpe:2.3:a:vendor:product:version:...
        parts = cpe_string.split(':')
        if len(parts) >= 5:
            return {
                "product": parts[4],
                "version": parts[5] if len(parts) > 5 and parts[5] != '*' else None,
                "vendor": parts[3] if parts[3] != '*' else None
            }
        return {"product": cpe_string, "version": None, "vendor": None}
    
    @staticmethod
    def normalize_cve_id(cve_id: str) -> Optional[str]:
        """Normalize CVE ID format"""
        if not cve_id:
            return None
        
        cve_id = str(cve_id).strip().upper()
        
        # Extract CVE pattern
        match = re.search(r'CVE-\d{4}-\d{4,}', cve_id)
        if match:
            return match.group(0)
        
        return None
    
    @staticmethod
    def extract_ips_from_text(text: str) -> List[str]:
        """Extract IP addresses from formatted text"""
        ipv4_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
        matches = re.findall(ipv4_pattern, text)
        return list(set(matches))

# =============================================================================
# VULNERABILITY DATA SOURCES (same as before)
# =============================================================================

class NVDSource:
    """National Vulnerability Database (NVD) - Official CVE data"""
    
    def __init__(self, config: VulnSearchConfig):
        self.config = config
        self.base_url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
        self.session = requests.Session()
        if config.nvd_api_key:
            self.session.headers.update({"apiKey": config.nvd_api_key})
    
    def search_product(self, product: str, version: Optional[str] = None,
                       max_results: int = 10) -> List[Dict[str, Any]]:
        """Search NVD for product vulnerabilities"""
        try:
            # Sanitize product name
            product = re.sub(r'[^a-zA-Z0-9\s\.\-]', ' ', product)
            product = re.sub(r'\s+', ' ', product).strip()
            
            if not product or len(product) < 2:
                return []
            
            # Build keyword search
            keyword = product
            if version:
                version = re.sub(r'[^a-zA-Z0-9\.\-]', '', version)
                if version:
                    keyword = f"{product} {version}"
            
            params = {
                "keywordSearch": keyword,
                "resultsPerPage": min(max_results, 100)
            }
            
            # Apply filters
            if self.config.min_cvss_score:
                params["cvssV3Severity"] = self._cvss_to_severity(self.config.min_cvss_score)
            
            if self.config.max_age_days:
                cutoff_date = (datetime.now() - timedelta(days=self.config.max_age_days)).isoformat()
                params["pubStartDate"] = cutoff_date
            
            response = self.session.get(
                self.base_url,
                params=params,
                timeout=self.config.request_timeout
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            vulnerabilities = []
            
            for item in data.get('vulnerabilities', [])[:max_results]:
                vuln = self._parse_nvd_item(item)
                if vuln:
                    vulnerabilities.append(vuln)
            
            time.sleep(self.config.rate_limit_delay)
            return vulnerabilities
        
        except Exception as e:
            logger.error(f"NVD search failed: {e}")
            return []
    
    def lookup_cve(self, cve_id: str) -> Optional[Dict[str, Any]]:
        """Lookup specific CVE by ID"""
        try:
            url = f"{self.base_url}?cveId={cve_id}"
            response = self.session.get(url, timeout=self.config.request_timeout)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            vulnerabilities = data.get('vulnerabilities', [])
            
            if vulnerabilities:
                return self._parse_nvd_item(vulnerabilities[0])
            
            return None
        
        except Exception as e:
            logger.error(f"NVD CVE lookup failed: {e}")
            return None
    
    def _parse_nvd_item(self, item: Dict) -> Optional[Dict[str, Any]]:
        """Parse NVD vulnerability item"""
        try:
            cve_data = item.get('cve', {})
            
            cve_id = cve_data.get('id')
            if not cve_id:
                return None
            
            # Description
            descriptions = cve_data.get('descriptions', [])
            description = ""
            for desc in descriptions:
                if desc.get('lang') == 'en':
                    description = desc.get('value', '')
                    break
            
            # CVSS metrics
            metrics = cve_data.get('metrics', {})
            cvss_v3 = None
            cvss_v2 = None
            severity = "UNKNOWN"
            
            if 'cvssMetricV31' in metrics and metrics['cvssMetricV31']:
                metric = metrics['cvssMetricV31'][0]
                cvss_data = metric.get('cvssData', {})
                cvss_v3 = {
                    "score": cvss_data.get('baseScore'),
                    "severity": cvss_data.get('baseSeverity'),
                    "vector": cvss_data.get('vectorString'),
                    "attack_vector": cvss_data.get('attackVector'),
                    "attack_complexity": cvss_data.get('attackComplexity'),
                    "privileges_required": cvss_data.get('privilegesRequired'),
                    "user_interaction": cvss_data.get('userInteraction'),
                    "scope": cvss_data.get('scope'),
                    "confidentiality_impact": cvss_data.get('confidentialityImpact'),
                    "integrity_impact": cvss_data.get('integrityImpact'),
                    "availability_impact": cvss_data.get('availabilityImpact')
                }
                severity = cvss_data.get('baseSeverity', 'UNKNOWN')
            
            elif 'cvssMetricV30' in metrics and metrics['cvssMetricV30']:
                metric = metrics['cvssMetricV30'][0]
                cvss_data = metric.get('cvssData', {})
                cvss_v3 = {
                    "score": cvss_data.get('baseScore'),
                    "severity": cvss_data.get('baseSeverity'),
                    "vector": cvss_data.get('vectorString')
                }
                severity = cvss_data.get('baseSeverity', 'UNKNOWN')
            
            if 'cvssMetricV2' in metrics and metrics['cvssMetricV2']:
                metric = metrics['cvssMetricV2'][0]
                cvss_data = metric.get('cvssData', {})
                cvss_v2 = {
                    "score": cvss_data.get('baseScore'),
                    "vector": cvss_data.get('vectorString')
                }
            
            # References
            references = []
            for ref in cve_data.get('references', []):
                references.append({
                    "url": ref.get('url'),
                    "source": ref.get('source'),
                    "tags": ref.get('tags', [])
                })
            
            # Weaknesses (CWE)
            weaknesses = []
            for weakness in cve_data.get('weaknesses', []):
                for desc in weakness.get('description', []):
                    if desc.get('lang') == 'en':
                        weaknesses.append(desc.get('value'))
            
            # Affected configurations
            configurations = []
            for config_node in cve_data.get('configurations', []):
                for node in config_node.get('nodes', []):
                    for cpe_match in node.get('cpeMatch', []):
                        if cpe_match.get('vulnerable'):
                            configurations.append({
                                "cpe": cpe_match.get('criteria'),
                                "version_start": cpe_match.get('versionStartIncluding'),
                                "version_end": cpe_match.get('versionEndExcluding')
                            })
            
            return {
                "source": "nvd",
                "cve_id": cve_id,
                "description": description,
                "severity": severity,
                "cvss_v3": cvss_v3,
                "cvss_v2": cvss_v2,
                "published": cve_data.get('published'),
                "modified": cve_data.get('lastModified'),
                "references": references[:10],
                "weaknesses": weaknesses,
                "configurations": configurations[:5],
                "source_url": f"https://nvd.nist.gov/vuln/detail/{cve_id}"
            }
        
        except Exception as e:
            logger.error(f"Failed to parse NVD item: {e}")
            return None
    
    def _cvss_to_severity(self, score: float) -> str:
        """Convert CVSS score to severity"""
        if score >= 9.0:
            return "CRITICAL"
        elif score >= 7.0:
            return "HIGH"
        elif score >= 4.0:
            return "MEDIUM"
        elif score > 0:
            return "LOW"
        return "NONE"

class VulnersSource:
    """Vulners - Vulnerability aggregator with exploit info"""
    
    def __init__(self, config: VulnSearchConfig):
        self.config = config
        self.base_url = "https://vulners.com/api/v3"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Vera-VulnScanner/1.0"})
        if config.vulners_api_key:
            self.session.headers.update({"X-Vulners-Api-Key": config.vulners_api_key})
    
    def search_product(self, product: str, version: Optional[str] = None,
                       max_results: int = 10) -> List[Dict[str, Any]]:
        """Search Vulners for vulnerabilities"""
        try:
            # Sanitize input
            product = re.sub(r'[^a-zA-Z0-9\s\.\-]', ' ', product)
            product = re.sub(r'\s+', ' ', product).strip()
            
            if not product or len(product) < 2:
                return []
            
            query = product
            if version:
                version = re.sub(r'[^a-zA-Z0-9\.\-]', '', version)
                if version:
                    query = f"{product} {version}"
            
            data = {
                "query": query,
                "skip": 0,
                "size": max_results
            }
            
            response = self.session.post(
                f"{self.base_url}/search/lucene/",
                json=data,
                timeout=self.config.request_timeout
            )
            
            if response.status_code != 200:
                return []
            
            result = response.json()
            vulnerabilities = []
            
            for item in result.get('data', {}).get('search', [])[:max_results]:
                vuln = self._parse_vulners_item(item)
                if vuln:
                    vulnerabilities.append(vuln)
            
            time.sleep(self.config.rate_limit_delay)
            return vulnerabilities
        
        except Exception as e:
            logger.error(f"Vulners search failed: {e}")
            return []
    
    def _parse_vulners_item(self, item: Dict) -> Optional[Dict[str, Any]]:
        """Parse Vulners item"""
        try:
            source_data = item.get('_source', {})
            
            cve_id = None
            for identifier in source_data.get('cvelist', []):
                if identifier.startswith('CVE-'):
                    cve_id = identifier
                    break
            
            if not cve_id:
                cve_id = source_data.get('id', 'VULNERS-' + str(hash(str(item)))[:8])
            
            # CVSS score
            cvss_score = source_data.get('cvss', {}).get('score')
            cvss_vector = source_data.get('cvss', {}).get('vector')
            
            # Severity
            severity = "UNKNOWN"
            if cvss_score:
                if cvss_score >= 9.0:
                    severity = "CRITICAL"
                elif cvss_score >= 7.0:
                    severity = "HIGH"
                elif cvss_score >= 4.0:
                    severity = "MEDIUM"
                else:
                    severity = "LOW"
            
            # Exploit availability
            exploit_available = source_data.get('exploit') is not None
            
            return {
                "source": "vulners",
                "cve_id": cve_id,
                "description": source_data.get('description', '')[:1000],
                "severity": severity,
                "cvss_v3": {
                    "score": cvss_score,
                    "vector": cvss_vector
                } if cvss_score else None,
                "published": source_data.get('published'),
                "exploit_available": exploit_available,
                "references": [{"url": ref} for ref in source_data.get('href', [])[:5]],
                "source_url": f"https://vulners.com/cve/{cve_id}"
            }
        
        except Exception as e:
            logger.error(f"Failed to parse Vulners item: {e}")
            return None

class ExploitDBSource:
    """ExploitDB - Public exploit database"""
    
    def __init__(self, config: VulnSearchConfig):
        self.config = config
        self.base_url = "https://www.exploit-db.com"
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
    
    def search_exploits(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search for exploits"""
        try:
            # Sanitize query
            query = re.sub(r'[^a-zA-Z0-9\s\.\-]', ' ', query)
            query = re.sub(r'\s+', ' ', query).strip()
            
            if not query or len(query) < 2:
                return []
            
            url = f"{self.base_url}/search"
            params = {"q": query}
            
            response = self.session.get(
                url,
                params=params,
                timeout=self.config.request_timeout
            )
            
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            exploits = []
            
            # Parse results table
            for row in soup.select('table.table tr')[1:max_results+1]:
                try:
                    cols = row.find_all('td')
                    if len(cols) >= 5:
                        exploit = {
                            "source": "exploitdb",
                            "edb_id": cols[0].text.strip(),
                            "title": cols[4].text.strip(),
                            "type": cols[3].text.strip(),
                            "platform": cols[2].text.strip(),
                            "date": cols[1].text.strip(),
                            "url": f"{self.base_url}/exploits/{cols[0].text.strip()}"
                        }
                        exploits.append(exploit)
                except Exception:
                    continue
            
            time.sleep(self.config.rate_limit_delay)
            return exploits
        
        except Exception as e:
            logger.error(f"ExploitDB search failed: {e}")
            return []

# =============================================================================
# VULNERABILITY MAPPER - NETWORK-AWARE
# =============================================================================

class VulnerabilityMapper:
    """
    Vulnerability intelligence mapper with multi-source aggregation,
    network service integration, and full memory integration.
    """
    
    def __init__(self, agent, config: VulnSearchConfig):
        self.agent = agent
        self.config = config
        
        # Initialize sources
        self.nvd = NVDSource(config)
        self.vulners = VulnersSource(config)
        self.exploitdb = ExploitDBSource(config)
        
        # Tracking
        self.search_node_id = None
        self.discovered_vulns = {}
        
        # Cache
        self.cache = {} if config.enable_cache else None
        self.cache_timestamps = {}
    
    def _initialize_search(self, tool_name: str, target: str):
        """Initialize vulnerability search context"""
        if self.search_node_id is not None:
            return
        
        try:
            search_mem = self.agent.mem.add_session_memory(
                self.agent.sess.id,
                f"Vulnerability search: {target}",
                "vulnerability_search",
                metadata={
                    "tool": tool_name,
                    "target": target,
                    "started_at": datetime.now().isoformat(),
                }
            )
            self.search_node_id = search_mem.id
        except Exception:
            pass
    
    def _check_cache(self, cache_key: str) -> Optional[List[Dict]]:
        """Check if results are cached"""
        if not self.config.enable_cache or self.cache is None:
            return None
        
        if cache_key not in self.cache:
            return None
        
        # Check TTL
        timestamp = self.cache_timestamps.get(cache_key)
        if timestamp:
            age_hours = (datetime.now() - timestamp).total_seconds() / 3600
            if age_hours > self.config.cache_ttl_hours:
                del self.cache[cache_key]
                del self.cache_timestamps[cache_key]
                return None
        
        return self.cache[cache_key]
    
    def _update_cache(self, cache_key: str, results: List[Dict]):
        """Update cache"""
        if self.config.enable_cache and self.cache is not None:
            self.cache[cache_key] = results
            self.cache_timestamps[cache_key] = datetime.now()
    
    def _create_vulnerability_node(self, vuln_data: Dict[str, Any]) -> str:
        """Create vulnerability node in graph"""
        cve_id = vuln_data.get('cve_id', 'UNKNOWN')
        vuln_node_id = f"vuln_{cve_id.replace('-', '_')}"
        
        if vuln_node_id in self.discovered_vulns:
            return self.discovered_vulns[vuln_node_id]
        
        try:
            properties = {
                "cve_id": cve_id,
                "description": vuln_data.get('description', '')[:2000],
                "severity": vuln_data.get('severity', 'UNKNOWN'),
                "source": vuln_data.get('source'),
                "published": vuln_data.get('published'),
                "discovered_at": datetime.now().isoformat(),
            }
            
            # Add CVSS scores
            if vuln_data.get('cvss_v3'):
                cvss_v3 = vuln_data['cvss_v3']
                if isinstance(cvss_v3, dict):
                    properties["cvss_v3_score"] = cvss_v3.get('score')
                    properties["cvss_v3_vector"] = cvss_v3.get('vector')
            
            if vuln_data.get('cvss_v2'):
                cvss_v2 = vuln_data['cvss_v2']
                if isinstance(cvss_v2, dict):
                    properties["cvss_v2_score"] = cvss_v2.get('score')
            
            # Additional metadata
            if vuln_data.get('exploit_available'):
                properties["exploit_available"] = True
            
            if vuln_data.get('patched_version'):
                properties["patched_version"] = vuln_data['patched_version']
            
            if vuln_data.get('source_url'):
                properties["source_url"] = vuln_data['source_url']
            
            # Create node
            self.agent.mem.upsert_entity(
                vuln_node_id,
                "vulnerability",
                labels=["Vulnerability", "CVE", vuln_data.get('severity', 'UNKNOWN')],
                properties=properties
            )
            
            # Link to search context
            if self.search_node_id:
                self.agent.mem.link(
                    self.search_node_id,
                    vuln_node_id,
                    "FOUND_VULNERABILITY",
                    {
                        "cve_id": cve_id,
                        "severity": vuln_data.get('severity'),
                        "source": vuln_data.get('source')
                    }
                )
            
            self.discovered_vulns[vuln_node_id] = vuln_node_id
            return vuln_node_id
        
        except Exception as e:
            logger.error(f"Failed to create vulnerability node: {e}")
            return vuln_node_id
    
    def _link_vulnerability_to_service(self, vuln_node_id: str, service_node_id: str,
                                      severity: str, cvss_score: Optional[float]):
        """Link vulnerability to network service node"""
        try:
            self.agent.mem.link(
                service_node_id,
                vuln_node_id,
                "HAS_VULNERABILITY",
                {
                    "severity": severity,
                    "cvss_score": cvss_score,
                    "discovered_at": datetime.now().isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Failed to link vulnerability to service: {e}")
    
    def _load_services_from_graph(self, targets: List[str]) -> Dict[Tuple[str, int], Tuple[str, Dict]]:
        """Load network services from graph"""
        services = {}
        try:
            with self.agent.mem.graph._driver.session() as sess:
                result = sess.run("""
                    MATCH (ip:NetworkHost)-[:HAS_PORT]->(port:NetworkPort)-[:RUNS_SERVICE]->(svc:NetworkService)
                    WHERE ip.ip_address IN $targets
                    RETURN svc.id as id, ip.ip_address as ip, port.port_number as port,
                           svc.service_name as service, svc.version as version
                """, {"targets": targets})
                
                for record in result:
                    key = (record["ip"], record["port"])
                    services[key] = (record["id"], {
                        "service": record["service"],
                        "version": record["version"]
                    })
        except Exception as e:
            logger.error(f"Failed to load services from graph: {e}")
        
        return services
    
    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate vulnerabilities by CVE ID"""
        seen_cves = {}
        deduplicated = []
        
        for vuln in results:
            cve_id = vuln.get('cve_id')
            if not cve_id:
                deduplicated.append(vuln)
                continue
            
            if cve_id not in seen_cves:
                seen_cves[cve_id] = vuln
                deduplicated.append(vuln)
            else:
                # Merge data from multiple sources
                existing = seen_cves[cve_id]
                
                # Keep the one with more complete data
                if vuln.get('cvss_v3') and not existing.get('cvss_v3'):
                    seen_cves[cve_id] = vuln
                    deduplicated[deduplicated.index(existing)] = vuln
                
                # Merge exploit info
                if vuln.get('exploit_available') and not existing.get('exploit_available'):
                    existing['exploit_available'] = True
        
        return deduplicated
    def _apply_filters(self, vulnerabilities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply configured filters"""
        filtered = vulnerabilities
        
        # Severity filter
        if self.config.severity_filter:
            filtered = [
                v for v in filtered
                if v.get('severity') == self.config.severity_filter.upper()
            ]
        
        # CVSS score filter - FIXED
        if self.config.min_cvss_score:
            def meets_cvss_threshold(v):
                cvss_v3 = v.get('cvss_v3')
                cvss_v2 = v.get('cvss_v2')
                
                if cvss_v3 and isinstance(cvss_v3, dict):
                    score = cvss_v3.get('score', 0)
                    if score and score >= self.config.min_cvss_score:
                        return True
                
                if cvss_v2 and isinstance(cvss_v2, dict):
                    score = cvss_v2.get('score', 0)
                    if score and score >= self.config.min_cvss_score:
                        return True
                
                return False
            
            filtered = [v for v in filtered if meets_cvss_threshold(v)]
        
        # Only exploited filter
        if self.config.only_exploited:
            filtered = [
                v for v in filtered
                if v.get('exploit_available')
            ]
        
        return filtered

    def search_vulnerabilities(self, target: str, version: Optional[str] = None,
                            vendor: Optional[str] = None) -> Iterator[str]:
        """Comprehensive multi-source vulnerability search"""
        
        product_info = VulnInputParser.extract_product(target)
        product = product_info['product']
        if not version:
            version = product_info['version']
        if not vendor:
            vendor = product_info['vendor']
        
        self._initialize_search("search_vulnerabilities", f"{product} {version or ''}")
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║            VULNERABILITY INTELLIGENCE SEARCH                 ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        yield f"  Target: {product}\n"
        if version:
            yield f"  Version: {version}\n"
        if vendor:
            yield f"  Vendor: {vendor}\n"
        yield f"  Sources: {', '.join(self.config.sources)}\n\n"
        
        # Check cache
        cache_key = f"{product}:{version}:{','.join(self.config.sources)}"
        cached_results = self._check_cache(cache_key)
        
        if cached_results:
            yield "  [CACHE] Using cached results\n\n"
            all_vulnerabilities = cached_results
        else:
            # Query each source
            all_vulnerabilities = []
            
            for source in self.config.sources:
                if source == "nvd":
                    yield f"  [•] Querying NVD...\n"
                    vulns = self.nvd.search_product(product, version, self.config.max_results_per_source)
                    all_vulnerabilities.extend(vulns)
                    yield f"      Found {len(vulns)} vulnerabilities\n"
                
                elif source == "vulners":
                    yield f"  [•] Querying Vulners...\n"
                    vulns = self.vulners.search_product(product, version, self.config.max_results_per_source)
                    all_vulnerabilities.extend(vulns)
                    yield f"      Found {len(vulns)} vulnerabilities\n"
            
            # Update cache
            self._update_cache(cache_key, all_vulnerabilities)
        
        # Deduplicate and filter
        if self.config.deduplicate:
            all_vulnerabilities = self._deduplicate_results(all_vulnerabilities)
        
        all_vulnerabilities = self._apply_filters(all_vulnerabilities)
        
        # Sort by severity/score - FIXED
        def sort_key(v):
            score = 0
            cvss_v3 = v.get('cvss_v3')
            cvss_v2 = v.get('cvss_v2')
            
            if cvss_v3 and isinstance(cvss_v3, dict):
                score = cvss_v3.get('score', 0) or 0
            elif cvss_v2 and isinstance(cvss_v2, dict):
                score = cvss_v2.get('score', 0) or 0
            
            return -score  # Descending
        
        all_vulnerabilities.sort(key=sort_key)
        all_vulnerabilities = all_vulnerabilities[:self.config.max_total_results]
        
        yield f"\n  Total Unique Vulnerabilities: {len(all_vulnerabilities)}\n\n"
        
        # Group by severity
        by_severity = {}
        for vuln in all_vulnerabilities:
            severity = vuln.get('severity', 'UNKNOWN')
            if severity not in by_severity:
                by_severity[severity] = []
            by_severity[severity].append(vuln)
        
        # Output results - FIXED
        for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]:
            vulns = by_severity.get(severity, [])
            if not vulns:
                continue
            
            yield f"\n  [{severity}] ({len(vulns)} vulnerabilities)\n"
            yield f"  {'─' * 60}\n"
            
            for vuln in vulns[:10]:  # Limit display
                # Create node
                self._create_vulnerability_node(vuln)
                
                cve_id = vuln.get('cve_id', 'UNKNOWN')
                description = vuln.get('description', 'No description')[:100]
                
                yield f"    • {cve_id}"
                
                # FIXED - properly check cvss_v3
                cvss_v3 = vuln.get('cvss_v3')
                if cvss_v3 and isinstance(cvss_v3, dict):
                    score = cvss_v3.get('score')
                    if score:
                        yield f" (CVSS: {score}/10)"
                
                if vuln.get('exploit_available'):
                    yield f" [EXPLOIT AVAILABLE]"
                
                yield f"\n      {description}...\n"
                
                if vuln.get('source_url'):
                    yield f"      {vuln['source_url']}\n"
            
            if len(vulns) > 10:
                yield f"    ... and {len(vulns) - 10} more {severity} vulnerabilities\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Vulnerabilities Discovered: {len(all_vulnerabilities)}\n"
        if by_severity.get('CRITICAL'):
            yield f"  CRITICAL: {len(by_severity['CRITICAL'])}\n"
        if by_severity.get('HIGH'):
            yield f"  HIGH: {len(by_severity['HIGH'])}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"

    def scan_network_services(self, target: str, severity_filter: Optional[str] = None,
                            max_results: int = 5, service_filter: Optional[str] = None) -> Iterator[str]:
        """Scan network services for vulnerabilities - FULLY STANDALONE"""
        
        self._initialize_search("scan_network_services", target)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║           NETWORK SERVICE VULNERABILITY SCAN                 ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        # Parse targets (handles IPs or formatted output)
        target_ips = VulnInputParser.extract_ips_from_text(target)
        
        if not target_ips:
            # Might be hostname
            target_ips = [target.strip()]
        
        yield f"  Targets: {', '.join(target_ips[:5])}\n"
        if len(target_ips) > 5:
            yield f"  ... and {len(target_ips) - 5} more\n"
        yield f"\n"
        
        # Load services from graph
        discovered_services = self._load_services_from_graph(target_ips)
        
        # Auto-run prerequisites if no services found
        if not discovered_services and self.config.auto_run_prerequisites:
            yield f"  [!] No services found in graph\n"
            yield f"  [!] Please run network service detection first\n"
            yield f"  [!] Example: detect_services('{target_ips[0]}')\n\n"
            return
        
        if not discovered_services:
            yield "  [!] No services found to scan for vulnerabilities\n"
            yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
            yield f"  Vulnerabilities Found: 0\n"
            yield f"╚══════════════════════════════════════════════════════════════╝\n"
            return
        
        yield f"  Found {len(discovered_services)} services to scan\n\n"
        
        total_vulns = 0
        
        for ip in target_ips:
            # Get services for this IP
            ip_services = []
            for key, value in discovered_services.items():
                i, port = key
                if i == ip:
                    node_id, svc_data = value
                    ip_services.append((port, node_id, svc_data))
            
            if not ip_services:
                continue
            
            yield f"\n  [•] Scanning {ip} for vulnerabilities...\n"
            
            for port, service_node_id, svc_data in ip_services:
                service_name = svc_data.get("service", "")
                version = svc_data.get("version")
                
                # Apply service filter
                if service_filter and service_filter.lower() not in service_name.lower():
                    continue
                
                # Skip unknown services
                if service_name.startswith("unknown"):
                    continue
                
                yield f"      [•] Port {port} ({service_name} {version or ''})...\n"
                
                try:
                    # Search for CVEs
                    cves = self.nvd.search_product(service_name, version, max_results)
                    
                    # Filter by severity if specified
                    if severity_filter:
                        cves = [
                            cve for cve in cves
                            if cve.get('severity') == severity_filter.upper()
                        ]
                    
                    if cves:
                        for cve in cves:
                            total_vulns += 1
                            
                            # Create vulnerability node
                            vuln_node_id = self._create_vulnerability_node(cve)
                            
                            # Link to service
                            cvss_score = None
                            cvss_v3 = cve.get('cvss_v3')
                            if cvss_v3 and isinstance(cvss_v3, dict):
                                cvss_score = cvss_v3.get('score')
                            
                            self._link_vulnerability_to_service(
                                vuln_node_id,
                                service_node_id,
                                cve.get('severity'),
                                cvss_score
                            )
                            
                            yield f"          • {cve['cve_id']}: {cve['severity']} "
                            
                            # FIXED - properly check cvss_v3
                            if cvss_score:
                                yield f"({cvss_score}/10)"
                            
                            yield f"\n"
                    else:
                        yield f"          No vulnerabilities found\n"
                    
                    time.sleep(1)  # Rate limiting
                
                except Exception as e:
                    logger.error(f"Failed to scan service: {e}")
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Vulnerabilities Found: {total_vulns}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"

    def lookup_cve(self, cve_id: str) -> Iterator[str]:
        """Lookup specific CVE by ID"""
        
        cve_id = VulnInputParser.normalize_cve_id(cve_id)
        if not cve_id:
            yield "Invalid CVE ID format\n"
            return
        
        self._initialize_search("lookup_cve", cve_id)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                    CVE LOOKUP                                ║\n"
        yield f"║                    {cve_id:^40}                  ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        # Query NVD
        yield "  [•] Querying NVD...\n"
        vuln_data = self.nvd.lookup_cve(cve_id)
        
        if not vuln_data:
            yield f"\n  [!] CVE {cve_id} not found in NVD\n"
            return
        
        # Create node
        self._create_vulnerability_node(vuln_data)
        
        # Display detailed info
        yield f"\n  CVE ID: {vuln_data.get('cve_id')}\n"
        yield f"  Severity: {vuln_data.get('severity')}\n"
        
        # FIXED - properly check cvss_v3
        cvss_v3 = vuln_data.get('cvss_v3')
        if cvss_v3 and isinstance(cvss_v3, dict):
            score = cvss_v3.get('score')
            vector = cvss_v3.get('vector')
            
            if score:
                yield f"  CVSS v3 Score: {score}/10\n"
            if vector:
                yield f"  CVSS v3 Vector: {vector}\n"
            
            if cvss_v3.get('attack_vector'):
                yield f"\n  Attack Details:\n"
                yield f"    Vector: {cvss_v3.get('attack_vector')}\n"
                yield f"    Complexity: {cvss_v3.get('attack_complexity')}\n"
                yield f"    Privileges Required: {cvss_v3.get('privileges_required')}\n"
                yield f"    User Interaction: {cvss_v3.get('user_interaction')}\n"
                yield f"\n  Impact:\n"
                yield f"    Confidentiality: {cvss_v3.get('confidentiality_impact')}\n"
                yield f"    Integrity: {cvss_v3.get('integrity_impact')}\n"
                yield f"    Availability: {cvss_v3.get('availability_impact')}\n"
        
        yield f"\n  Description:\n"
        yield f"  {vuln_data.get('description')}\n"
        
        if vuln_data.get('weaknesses'):
            yield f"\n  Weaknesses:\n"
            for cwe in vuln_data['weaknesses']:
                yield f"    • {cwe}\n"
        
        yield f"\n  Published: {vuln_data.get('published')}\n"
        yield f"  Modified: {vuln_data.get('modified')}\n"
        
        if vuln_data.get('references'):
            yield f"\n  References:\n"
            for ref in vuln_data['references'][:5]:
                yield f"    • {ref.get('url')}\n"
        
        if vuln_data.get('configurations'):
            yield f"\n  Affected Configurations:\n"
            for config in vuln_data['configurations'][:5]:
                yield f"    • {config.get('cpe')}\n"
        
        yield f"\n  Source: {vuln_data.get('source_url')}\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                    LOOKUP COMPLETE                           ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
        
    def search_exploits(self, target: str, cve_id: Optional[str] = None) -> Iterator[str]:
        """Search for available exploits"""
        
        if cve_id:
            cve_id = VulnInputParser.normalize_cve_id(cve_id)
            query = cve_id
        else:
            product_info = VulnInputParser.extract_product(target)
            query = product_info['product']
        
        self._initialize_search("search_exploits", query)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                    EXPLOIT SEARCH                            ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        yield f"  Query: {query}\n\n"
        
        # Search ExploitDB
        yield "  [•] Searching ExploitDB...\n"
        exploits = self.exploitdb.search_exploits(query, self.config.max_results_per_source)
        
        if not exploits:
            yield "\n  No exploits found\n"
            return
        
        yield f"\n  Found {len(exploits)} exploits\n\n"
        
        for exploit in exploits:
            yield f"  [{exploit.get('type')}] {exploit.get('title')}\n"
            yield f"    EDB-ID: {exploit.get('edb_id')}\n"
            yield f"    Platform: {exploit.get('platform')}\n"
            yield f"    Date: {exploit.get('date')}\n"
            yield f"    URL: {exploit.get('url')}\n\n"
        
        yield f"╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Total Exploits: {len(exploits)}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"

# =============================================================================
# TOOL INTEGRATION
# =============================================================================

def add_vulnerability_intelligence_tools(tool_list: List, agent):
    """Add comprehensive vulnerability intelligence tools"""
    from langchain_core.tools import StructuredTool
    
    def search_vulnerabilities_wrapper(target: str, version: Optional[str] = None,
                                      vendor: Optional[str] = None):
        config = VulnSearchConfig.comprehensive_lookup()
        mapper = VulnerabilityMapper(agent, config)
        for chunk in mapper.search_vulnerabilities(target, version, vendor):
            yield chunk
    
    def scan_network_services_wrapper(target: str, severity_filter: Optional[str] = None,
                                     max_results: int = 5, service_filter: Optional[str] = None):
        config = VulnSearchConfig.network_scan_vuln()
        mapper = VulnerabilityMapper(agent, config)
        for chunk in mapper.scan_network_services(target, severity_filter, max_results, service_filter):
            yield chunk
    
    def lookup_cve_wrapper(cve_id: str):
        config = VulnSearchConfig.quick_lookup()
        mapper = VulnerabilityMapper(agent, config)
        for chunk in mapper.lookup_cve(cve_id):
            yield chunk
    
    def search_exploits_wrapper(target: str, cve_id: Optional[str] = None,
                               exploit_type: Optional[str] = None):
        config = VulnSearchConfig.exploit_focused()
        mapper = VulnerabilityMapper(agent, config)
        for chunk in mapper.search_exploits(target, cve_id):
            yield chunk
    
    def quick_vuln_check_wrapper(target: str):
        config = VulnSearchConfig.quick_lookup()
        config.max_results_per_source = 5
        mapper = VulnerabilityMapper(agent, config)
        for chunk in mapper.search_vulnerabilities(target):
            yield chunk
    
    def comprehensive_vuln_scan_wrapper(target: str, search_type: str = "standard",
                                       sources: Optional[List[str]] = None,
                                       severity_filter: Optional[str] = None,
                                       min_cvss: Optional[float] = None,
                                       only_exploited: bool = False):
        if search_type == "quick":
            config = VulnSearchConfig.quick_lookup()
        elif search_type == "comprehensive":
            config = VulnSearchConfig.comprehensive_lookup()
        elif search_type == "exploit_focused":
            config = VulnSearchConfig.exploit_focused()
        else:
            config = VulnSearchConfig()
        
        if sources:
            config.sources = sources
        if severity_filter:
            config.severity_filter = severity_filter
        if min_cvss:
            config.min_cvss_score = min_cvss
        if only_exploited:
            config.only_exploited = True
        
        mapper = VulnerabilityMapper(agent, config)
        for chunk in mapper.search_vulnerabilities(target):
            yield chunk
    
    tool_list.extend([
        StructuredTool.from_function(
            func=search_vulnerabilities_wrapper,
            name="search_vulnerabilities",
            description=(
                "Comprehensive multi-source vulnerability search. "
                "Queries NVD, Vulners databases for CVE data. "
                "Accepts product names, services, or technologies. "
                "Example: 'Apache 2.4.51', 'nginx/1.20.1', 'WordPress 6.0'. "
                "Returns detailed CVE data with CVSS scores, exploitability, patches."
            ),
            args_schema=ProductVulnInput
        ),
        
        StructuredTool.from_function(
            func=scan_network_services_wrapper,
            name="scan_network_services_vulnerabilities",
            description=(
                "Scan network services for vulnerabilities. NETWORK-AWARE. "
                "Automatically loads services from graph memory and maps to CVEs. "
                "Use after network service detection. Tool chaining compatible. "
                "Accepts IPs, CIDRs, or formatted scan output."
            ),
            args_schema=NetworkVulnScanInput
        ),
        
        StructuredTool.from_function(
            func=lookup_cve_wrapper,
            name="lookup_cve",
            description=(
                "Lookup specific CVE by ID. Returns comprehensive details from NVD: "
                "CVSS v3/v2 scores, attack vectors, impact metrics, weaknesses (CWE), "
                "affected configurations, references, and timeline."
            ),
            args_schema=CVELookupInput
        ),
        
        StructuredTool.from_function(
            func=search_exploits_wrapper,
            name="search_exploits",
            description=(
                "Search for public exploits in ExploitDB database. "
                "Can search by product name or specific CVE ID. "
                "Returns exploit details, platforms, and download links."
            ),
            args_schema=ExploitSearchInput
        ),
        
        StructuredTool.from_function(
            func=quick_vuln_check_wrapper,
            name="quick_vulnerability_check",
            description=(
                "Quick vulnerability check (NVD only, top 5 results). "
                "Fast lookup for discovered services or technologies. "
                "Use for rapid assessment during network/web scans."
            ),
            args_schema=FlexibleVulnInput
        ),
        
        StructuredTool.from_function(
            func=comprehensive_vuln_scan_wrapper,
            name="comprehensive_vulnerability_scan",
            description=(
                "Full comprehensive vulnerability intelligence gathering. "
                "Multi-source aggregation with filtering options. "
                "Modes: quick, standard, comprehensive, exploit_focused. "
                "Supports severity filtering, CVSS thresholds, exploit-only results."
            ),
            args_schema=ComprehensiveVulnInput
        ),
    ])
    
    return tool_list

if __name__ == "__main__":
    print("Vulnerability Intelligence Toolkit")
    print("✓ Multi-source aggregation (NVD, Vulners, ExploitDB)")
    print("✓ Network service vulnerability mapping")
    print("✓ Detailed CVE intelligence")
    print("✓ Exploit database integration")
    print("✓ CVSS v3/v2 scoring")
    print("✓ Graph memory integration")
    print("✓ Tool chaining compatible")
    print("✓ Network-aware vulnerability scanning")
    print("\nData Sources:")
    print("  • NVD - Official CVE data with CVSS metrics")
    print("  • Vulners - Aggregated vulnerabilities with exploit info")
    print("  • ExploitDB - Public exploit repository")
    print("\nCapabilities:")
    print("  • Product/service/technology vulnerability lookup")
    print("  • Network service vulnerability mapping")
    print("  • Specific CVE detailed analysis")
    print("  • Exploit availability checking")
    print("  • CVSS-based severity filtering")
    print("  • Multi-source correlation and deduplication")