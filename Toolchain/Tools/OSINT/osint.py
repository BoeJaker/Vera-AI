"""
OSINT (Open Source Intelligence) Toolkit for Vera
==================================================
Comprehensive intelligence gathering tools for security research,
reconnaissance, and open-source information collection.

Features:
- CVE (Common Vulnerabilities and Exposures) search and analysis
- Social media profile discovery and scanning
- Subdomain enumeration and fuzzing
- Playwright-based web scraping and interaction
- DNS reconnaissance
- WHOIS lookups
- SSL/TLS certificate analysis
- Email harvesting
- Breach data checking
- Technology fingerprinting
- Metadata extraction

IMPORTANT: Use responsibly and ethically. Only scan targets you have permission to test.

Dependencies:
    pip install playwright dnspython python-whois requests beautifulsoup4 
    pip install censys shodan builtwith pytz
    playwright install chromium
"""

import asyncio
import json
import re
import socket
import ssl
import time
import hashlib
import base64
from typing import List, Dict, Any, Optional, Set, Tuple
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, urljoin
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

# DNS and network tools
try:
    import dns.resolver
    import dns.reversename
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False
    print("[Warning] dnspython not available - DNS features disabled")

# WHOIS
try:
    import whois as python_whois
    WHOIS_AVAILABLE = True
except ImportError:
    WHOIS_AVAILABLE = False
    print("[Warning] python-whois not available - WHOIS features disabled")

# Playwright for web automation
try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("[Warning] Playwright not available - web automation features disabled")

# HTTP requests
import requests
from requests.exceptions import RequestException

# HTML parsing
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("[Warning] BeautifulSoup not available - HTML parsing limited")


# ============================================================================
# INPUT SCHEMAS
# ============================================================================

class CVESearchInput(BaseModel):
    """Input schema for CVE search."""
    query: str = Field(..., description="CVE ID (e.g., CVE-2021-44228) or product name to search")
    year: Optional[int] = Field(default=None, description="Filter by year")
    severity: Optional[str] = Field(
        default=None,
        description="Filter by severity: CRITICAL, HIGH, MEDIUM, LOW"
    )
    limit: int = Field(default=10, description="Maximum results to return")


class SubdomainEnumInput(BaseModel):
    """Input schema for subdomain enumeration."""
    domain: str = Field(..., description="Root domain to enumerate (e.g., example.com)")
    method: str = Field(
        default="passive",
        description="Method: passive (safe), bruteforce (aggressive), hybrid"
    )
    wordlist: Optional[str] = Field(
        default="common",
        description="Wordlist: common, extensive, custom_path"
    )
    timeout: int = Field(default=5, description="DNS timeout in seconds")
    max_subdomains: int = Field(default=100, description="Maximum subdomains to find")


class SocialScanInput(BaseModel):
    """Input schema for social media scanning."""
    username: str = Field(..., description="Username to search across platforms")
    platforms: Optional[List[str]] = Field(
        default=None,
        description="Platforms: twitter, github, linkedin, instagram, reddit, youtube"
    )
    deep_scan: bool = Field(
        default=False,
        description="Perform deep scan (slower but more thorough)"
    )


class WebReconInput(BaseModel):
    """Input schema for web reconnaissance."""
    url: str = Field(..., description="Target URL to analyze")
    checks: List[str] = Field(
        default=["headers", "technologies", "ssl", "dns"],
        description="Checks: headers, technologies, ssl, dns, cookies, forms, links"
    )
    screenshot: bool = Field(default=False, description="Capture screenshot")


class EmailHarvestInput(BaseModel):
    """Input schema for email harvesting."""
    domain: str = Field(..., description="Domain to harvest emails from")
    sources: List[str] = Field(
        default=["web", "dns"],
        description="Sources: web, dns, search_engines"
    )
    limit: int = Field(default=50, description="Maximum emails to find")


class BreachCheckInput(BaseModel):
    """Input schema for breach data checking."""
    email: Optional[str] = Field(default=None, description="Email to check")
    username: Optional[str] = Field(default=None, description="Username to check")
    domain: Optional[str] = Field(default=None, description="Domain to check")


class DNSReconInput(BaseModel):
    """Input schema for DNS reconnaissance."""
    domain: str = Field(..., description="Domain for DNS reconnaissance")
    record_types: List[str] = Field(
        default=["A", "AAAA", "MX", "NS", "TXT", "CNAME"],
        description="DNS record types to query"
    )
    check_zone_transfer: bool = Field(
        default=False,
        description="Attempt zone transfer (may be logged)"
    )


class TechFingerprintInput(BaseModel):
    """Input schema for technology fingerprinting."""
    url: str = Field(..., description="URL to fingerprint")
    methods: List[str] = Field(
        default=["headers", "html", "scripts", "meta"],
        description="Detection methods"
    )


class PlaywrightScraperInput(BaseModel):
    """Input schema for Playwright-based scraping."""
    url: str = Field(..., description="URL to scrape")
    selectors: Optional[Dict[str, str]] = Field(
        default=None,
        description="CSS selectors to extract: {'name': 'selector'}"
    )
    javascript: Optional[str] = Field(
        default=None,
        description="JavaScript to execute on page"
    )
    wait_for: Optional[str] = Field(
        default=None,
        description="Selector to wait for before scraping"
    )
    screenshot: bool = Field(default=False, description="Take screenshot")


class WHOISLookupInput(BaseModel):
    """Input schema for WHOIS lookup."""
    domain: str = Field(..., description="Domain or IP address")
    parse_details: bool = Field(
        default=True,
        description="Parse and structure WHOIS data"
    )


# ============================================================================
# OSINT TOOLS CLASS
# ============================================================================

class OSINTTools:
    """Comprehensive OSINT toolkit for intelligence gathering."""
    
    def __init__(self, agent):
        self.agent = agent
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Common subdomain wordlist
        self.common_subdomains = [
            "www", "mail", "ftp", "localhost", "webmail", "smtp", "pop", "ns1", "ns2",
            "admin", "blog", "dev", "test", "staging", "api", "m", "mobile", "store",
            "shop", "app", "vpn", "ssh", "remote", "secure", "webdisk", "portal",
            "support", "help", "docs", "wiki", "forum", "cdn", "static", "assets"
        ]
    
    # ------------------------------------------------------------------------
    # CVE SEARCH & VULNERABILITY INTELLIGENCE
    # ------------------------------------------------------------------------
    
    def search_cve(self, query: str, year: Optional[int] = None,
                   severity: Optional[str] = None, limit: int = 10) -> str:
        """
        Search CVE (Common Vulnerabilities and Exposures) database.
        
        Search for known vulnerabilities by CVE ID, product name, or vendor.
        Uses multiple free CVE databases and aggregates results.
        
        Sources:
        - NVD (National Vulnerability Database)
        - CVE.org
        - CIRCL CVE Search
        
        Args:
            query: CVE ID (e.g., CVE-2021-44228) or product/vendor name
            year: Filter by year
            severity: Filter by severity level
            limit: Maximum results
        
        Returns: CVE details including CVSS scores, descriptions, and references
        
        Example:
            search_cve(query="log4j", severity="CRITICAL")
            search_cve(query="CVE-2021-44228")
        """
        try:
            results = {
                "query": query,
                "filters": {"year": year, "severity": severity},
                "cves": [],
                "summary": {}
            }
            
            # Check if it's a specific CVE ID
            cve_pattern = r'CVE-\d{4}-\d{4,}'
            is_cve_id = re.match(cve_pattern, query, re.IGNORECASE)
            
            if is_cve_id:
                # Search for specific CVE
                cve_id = query.upper()
                
                # Try NVD API
                try:
                    nvd_url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
                    response = self.session.get(nvd_url, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        if "vulnerabilities" in data and data["vulnerabilities"]:
                            vuln = data["vulnerabilities"][0]["cve"]
                            
                            # Extract CVSS scores
                            cvss_scores = {}
                            if "metrics" in vuln:
                                metrics = vuln["metrics"]
                                if "cvssMetricV31" in metrics and metrics["cvssMetricV31"]:
                                    cvss_v3 = metrics["cvssMetricV31"][0]["cvssData"]
                                    cvss_scores["v3"] = {
                                        "score": cvss_v3.get("baseScore"),
                                        "severity": cvss_v3.get("baseSeverity"),
                                        "vector": cvss_v3.get("vectorString")
                                    }
                            
                            # Extract description
                            description = ""
                            if "descriptions" in vuln:
                                for desc in vuln["descriptions"]:
                                    if desc.get("lang") == "en":
                                        description = desc.get("value", "")
                                        break
                            
                            # Extract references
                            references = []
                            if "references" in vuln:
                                references = [ref.get("url") for ref in vuln["references"][:5]]
                            
                            results["cves"].append({
                                "id": cve_id,
                                "description": description[:500],
                                "cvss": cvss_scores,
                                "published": vuln.get("published", ""),
                                "references": references
                            })
                except Exception as e:
                    print(f"NVD API error: {e}")
                
                # Try CIRCL CVE Search API
                try:
                    circl_url = f"https://cve.circl.lu/api/cve/{cve_id}"
                    response = self.session.get(circl_url, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        if not results["cves"]:  # Add if not already found
                            results["cves"].append({
                                "id": cve_id,
                                "description": data.get("summary", "")[:500],
                                "cvss": {"score": data.get("cvss")},
                                "published": data.get("Published", ""),
                                "references": data.get("references", [])[:5]
                            })
                except:
                    pass
            
            else:
                # Search by product/vendor name
                # Try CVE.org search
                try:
                    # Note: This is a simplified search - real implementation would use proper API
                    search_url = f"https://cve.circl.lu/api/search/{query}"
                    response = self.session.get(search_url, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        for item in data[:limit]:
                            cve_id = item.get("id", "")
                            
                            # Apply filters
                            if year:
                                cve_year = int(cve_id.split("-")[1]) if "-" in cve_id else 0
                                if cve_year != year:
                                    continue
                            
                            if severity:
                                cvss = item.get("cvss", 0)
                                item_severity = self._cvss_to_severity(cvss)
                                if item_severity != severity.upper():
                                    continue
                            
                            results["cves"].append({
                                "id": cve_id,
                                "description": item.get("summary", "")[:300],
                                "cvss": {"score": item.get("cvss")},
                                "published": item.get("Published", "")
                            })
                            
                            if len(results["cves"]) >= limit:
                                break
                except:
                    pass
            
            # Summary
            if results["cves"]:
                severities = [self._cvss_to_severity(cve.get("cvss", {}).get("score", 0))
                             for cve in results["cves"]]
                
                results["summary"] = {
                    "total_found": len(results["cves"]),
                    "critical": severities.count("CRITICAL"),
                    "high": severities.count("HIGH"),
                    "medium": severities.count("MEDIUM"),
                    "low": severities.count("LOW")
                }
            
            # Store in agent memory
            if results["cves"]:
                self.agent.mem.add_session_memory(
                    self.agent.sess.id,
                    f"CVE search: {query}",
                    "osint_cve",
                    metadata={"query": query, "results": len(results["cves"])}
                )
            
            return json.dumps(results, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "query": query
            })
    
    def _cvss_to_severity(self, score: float) -> str:
        """Convert CVSS score to severity level."""
        if score >= 9.0:
            return "CRITICAL"
        elif score >= 7.0:
            return "HIGH"
        elif score >= 4.0:
            return "MEDIUM"
        else:
            return "LOW"
    
    # ------------------------------------------------------------------------
    # SUBDOMAIN ENUMERATION
    # ------------------------------------------------------------------------
    
    def enumerate_subdomains(self, domain: str, method: str = "passive",
                            wordlist: str = "common", timeout: int = 5,
                            max_subdomains: int = 100) -> str:
        """
        Enumerate subdomains for a target domain.
        
        Methods:
        - Passive: Safe, uses certificate transparency logs and DNS databases
        - Bruteforce: Active DNS queries using wordlist
        - Hybrid: Combines both approaches
        
        IMPORTANT: Bruteforce method may trigger rate limiting or alerts.
        Only use on domains you have permission to test.
        
        Args:
            domain: Root domain (e.g., example.com)
            method: Enumeration method
            wordlist: Subdomain wordlist to use
            timeout: DNS query timeout
            max_subdomains: Maximum subdomains to find
        
        Returns: List of discovered subdomains with IP addresses and status
        
        Example:
            enumerate_subdomains("example.com", method="passive")
            enumerate_subdomains("example.com", method="bruteforce", wordlist="common")
        """
        try:
            if not DNS_AVAILABLE:
                return json.dumps({
                    "error": "DNS resolution not available - install dnspython"
                })
            
            results = {
                "domain": domain,
                "method": method,
                "subdomains": [],
                "summary": {}
            }
            
            found_subdomains = set()
            
            # Passive enumeration
            if method in ["passive", "hybrid"]:
                # Certificate Transparency Logs
                try:
                    ct_url = f"https://crt.sh/?q=%.{domain}&output=json"
                    response = self.session.get(ct_url, timeout=15)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        for entry in data:
                            name_value = entry.get("name_value", "")
                            subdomains = name_value.split("\n")
                            
                            for subdomain in subdomains:
                                subdomain = subdomain.strip()
                                if subdomain.endswith(f".{domain}") or subdomain == domain:
                                    found_subdomains.add(subdomain)
                                    
                                    if len(found_subdomains) >= max_subdomains:
                                        break
                except Exception as e:
                    print(f"Certificate transparency error: {e}")
                
                # DNS Database (VirusTotal, DNSDumpster alternative)
                # Note: Implement with proper API keys if available
            
            # Bruteforce enumeration
            if method in ["bruteforce", "hybrid"]:
                # Select wordlist
                if wordlist == "common":
                    wordlist_items = self.common_subdomains
                elif wordlist == "extensive":
                    wordlist_items = self.common_subdomains + [
                        f"web{i}" for i in range(1, 11)
                    ] + [f"server{i}" for i in range(1, 11)]
                else:
                    # Custom wordlist path
                    try:
                        with open(wordlist, 'r') as f:
                            wordlist_items = [line.strip() for line in f if line.strip()]
                    except:
                        wordlist_items = self.common_subdomains
                
                # Resolve each subdomain
                resolver = dns.resolver.Resolver()
                resolver.timeout = timeout
                resolver.lifetime = timeout
                
                for subdomain_prefix in wordlist_items:
                    if len(found_subdomains) >= max_subdomains:
                        break
                    
                    test_domain = f"{subdomain_prefix}.{domain}"
                    
                    if test_domain in found_subdomains:
                        continue
                    
                    try:
                        answers = resolver.resolve(test_domain, 'A')
                        if answers:
                            found_subdomains.add(test_domain)
                    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
                        pass
                    except dns.resolver.Timeout:
                        pass
                    except Exception:
                        pass
            
            # Resolve IP addresses for found subdomains
            resolver = dns.resolver.Resolver()
            resolver.timeout = timeout
            
            for subdomain in sorted(found_subdomains):
                if len(results["subdomains"]) >= max_subdomains:
                    break
                
                subdomain_info = {
                    "subdomain": subdomain,
                    "ip_addresses": [],
                    "cname": None,
                    "status": "active"
                }
                
                # Try to resolve A record
                try:
                    answers = resolver.resolve(subdomain, 'A')
                    subdomain_info["ip_addresses"] = [str(rdata) for rdata in answers]
                except:
                    pass
                
                # Try to resolve CNAME
                try:
                    answers = resolver.resolve(subdomain, 'CNAME')
                    if answers:
                        subdomain_info["cname"] = str(answers[0])
                except:
                    pass
                
                # Check if it's alive
                try:
                    response = self.session.get(
                        f"http://{subdomain}",
                        timeout=3,
                        allow_redirects=False
                    )
                    subdomain_info["http_status"] = response.status_code
                except:
                    subdomain_info["http_status"] = None
                
                results["subdomains"].append(subdomain_info)
            
            # Summary
            results["summary"] = {
                "total_found": len(results["subdomains"]),
                "method_used": method,
                "with_ip": len([s for s in results["subdomains"] if s["ip_addresses"]]),
                "http_accessible": len([s for s in results["subdomains"] if s.get("http_status")])
            }
            
            # Store in agent memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                f"Subdomain enumeration: {domain}",
                "osint_subdomains",
                metadata={
                    "domain": domain,
                    "found": len(results["subdomains"]),
                    "method": method
                }
            )
            
            return json.dumps(results, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "domain": domain
            })
    
    # ------------------------------------------------------------------------
    # SOCIAL MEDIA SCANNING
    # ------------------------------------------------------------------------
    
    def scan_social_profiles(self, username: str, platforms: Optional[List[str]] = None,
                            deep_scan: bool = False) -> str:
        """
        Scan social media platforms for a username.
        
        Checks username availability and profile existence across:
        - Twitter/X
        - GitHub
        - LinkedIn
        - Instagram
        - Reddit
        - YouTube
        - TikTok
        - Facebook
        - And more...
        
        Args:
            username: Username to search for
            platforms: Specific platforms to check (or None for all)
            deep_scan: Perform detailed profile analysis (slower)
        
        Returns: Profile existence, URLs, and metadata
        
        Example:
            scan_social_profiles(username="john_doe")
            scan_social_profiles(username="john_doe", platforms=["github", "twitter"])
        """
        try:
            results = {
                "username": username,
                "scan_type": "deep" if deep_scan else "quick",
                "profiles": [],
                "summary": {}
            }
            
            # Platform URL templates
            platform_urls = {
                "github": f"https://github.com/{username}",
                "twitter": f"https://twitter.com/{username}",
                "instagram": f"https://www.instagram.com/{username}/",
                "reddit": f"https://www.reddit.com/user/{username}",
                "youtube": f"https://www.youtube.com/@{username}",
                "linkedin": f"https://www.linkedin.com/in/{username}",
                "tiktok": f"https://www.tiktok.com/@{username}",
                "facebook": f"https://www.facebook.com/{username}",
                "medium": f"https://medium.com/@{username}",
                "dev.to": f"https://dev.to/{username}",
                "pinterest": f"https://www.pinterest.com/{username}",
                "twitch": f"https://www.twitch.tv/{username}",
                "spotify": f"https://open.spotify.com/user/{username}",
                "soundcloud": f"https://soundcloud.com/{username}",
                "vimeo": f"https://vimeo.com/{username}",
                "patreon": f"https://www.patreon.com/{username}",
                "dribbble": f"https://dribbble.com/{username}",
                "behance": f"https://www.behance.net/{username}",
                "stackoverflow": f"https://stackoverflow.com/users/{username}",
            }
            
            # Filter platforms if specified
            if platforms:
                platform_urls = {k: v for k, v in platform_urls.items() if k in platforms}
            
            # Check each platform
            for platform, url in platform_urls.items():
                profile_info = {
                    "platform": platform,
                    "url": url,
                    "exists": False,
                    "status_code": None,
                    "metadata": {}
                }
                
                try:
                    response = self.session.get(
                        url,
                        timeout=10,
                        allow_redirects=True
                    )
                    
                    profile_info["status_code"] = response.status_code
                    
                    # Check if profile exists
                    if response.status_code == 200:
                        # Platform-specific existence checks
                        if platform == "github":
                            if "Not Found" not in response.text:
                                profile_info["exists"] = True
                                
                                # Extract metadata for GitHub
                                if deep_scan and BS4_AVAILABLE:
                                    soup = BeautifulSoup(response.text, 'html.parser')
                                    
                                    # Try to get profile info
                                    name_elem = soup.select_one('[itemprop="name"]')
                                    if name_elem:
                                        profile_info["metadata"]["name"] = name_elem.text.strip()
                                    
                                    bio_elem = soup.select_one('[data-bio-text]')
                                    if bio_elem:
                                        profile_info["metadata"]["bio"] = bio_elem.text.strip()[:200]
                        
                        elif platform == "twitter":
                            # Twitter returns 200 even for non-existent users, check content
                            if "This account doesn't exist" not in response.text:
                                profile_info["exists"] = True
                        
                        elif platform == "reddit":
                            if response.url == url:  # Not redirected
                                profile_info["exists"] = True
                        
                        else:
                            # Generic check
                            profile_info["exists"] = True
                    
                    elif response.status_code == 404:
                        profile_info["exists"] = False
                    
                except RequestException as e:
                    profile_info["error"] = str(e)[:100]
                except Exception as e:
                    profile_info["error"] = str(e)[:100]
                
                results["profiles"].append(profile_info)
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
            
            # Summary
            results["summary"] = {
                "total_checked": len(results["profiles"]),
                "found": len([p for p in results["profiles"] if p["exists"]]),
                "not_found": len([p for p in results["profiles"] if not p["exists"] and p["status_code"]]),
                "errors": len([p for p in results["profiles"] if "error" in p])
            }
            
            # Store in agent memory
            if results["summary"]["found"] > 0:
                self.agent.mem.add_session_memory(
                    self.agent.sess.id,
                    f"Social scan: {username}",
                    "osint_social",
                    metadata={
                        "username": username,
                        "profiles_found": results["summary"]["found"]
                    }
                )
            
            return json.dumps(results, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "username": username
            })
    
    # ------------------------------------------------------------------------
    # Continue in next message due to length...
    # ------------------------------------------------------------------------


# Note: Due to length constraints, I'll create this as a multi-file toolkit
# File 1: Core OSINT (CVE, Subdomains, Social)
# File 2: Web Recon & Playwright Tools
# File 3: DNS, WHOIS, Email Harvesting