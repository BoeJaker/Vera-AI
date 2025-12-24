"""
OSINT Toolkit Integration & Tool Loader
========================================
Complete integration for all OSINT tools.

Usage:
    from Vera.Toolchain.Tools.osint_integration import add_all_osint_tools
    
    # In ToolLoader:
    add_all_osint_tools(tool_list, agent)
"""

from typing import List
from langchain_core.tools import StructuredTool

# Import all OSINT components
try:
    from Vera.Toolchain.Tools.OSINT.osint import (
        OSINTTools, CVESearchInput, SubdomainEnumInput, SocialScanInput
    )
    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False
    print("[Warning] OSINT core tools not available")

try:
    from Vera.Toolchain.Tools.OSINT.webrecon import (
        WebReconTools, WebReconInput, PlaywrightScraperInput, TechFingerprintInput
    )
    WEBRECON_AVAILABLE = True
except ImportError:
    WEBRECON_AVAILABLE = False
    print("[Warning] Web recon tools not available")


# ============================================================================
# COMPLETE TOOL LOADER
# ============================================================================

def add_all_osint_tools(tool_list: List, agent):
    """
    Add all OSINT tools to the tool list.
    
    Includes:
    - CVE search and vulnerability intelligence
    - Subdomain enumeration (passive & active)
    - Social media profile scanning
    - Web reconnaissance
    - Playwright-based scraping
    - Technology fingerprinting
    - DNS reconnaissance
    - WHOIS lookups
    - Email harvesting
    
    Call this in your ToolLoader function:
        from osint_integration import add_all_osint_tools
        add_all_osint_tools(tool_list, agent)
    
    IMPORTANT: Use responsibly and ethically.
    Only perform reconnaissance on systems you have permission to test.
    """
    
    # Core OSINT tools
    if CORE_AVAILABLE:
        osint = OSINTTools(agent)
        
        tool_list.extend([
            StructuredTool.from_function(
                func=osint.search_cve,
                name="osint_cve_search",
                description=(
                    "Search CVE database for vulnerabilities. "
                    "Find CVEs by ID, product name, or vendor. "
                    "Returns CVSS scores, descriptions, and references. "
                    "Example: search_cve('log4j', severity='CRITICAL')"
                ),
                args_schema=CVESearchInput
            ),
            
            StructuredTool.from_function(
                func=osint.enumerate_subdomains,
                name="osint_subdomain_enum",
                description=(
                    "Enumerate subdomains for a target domain. "
                    "Methods: passive (safe, uses CT logs), bruteforce (DNS queries), hybrid. "
                    "IMPORTANT: Only use on domains you have permission to test. "
                    "Example: enumerate_subdomains('example.com', method='passive')"
                ),
                args_schema=SubdomainEnumInput
            ),
            
            StructuredTool.from_function(
                func=osint.scan_social_profiles,
                name="osint_social_scan",
                description=(
                    "Scan social media platforms for username. "
                    "Checks GitHub, Twitter, LinkedIn, Instagram, Reddit, YouTube, and more. "
                    "Returns profile existence and URLs. "
                    "Example: scan_social_profiles('johndoe')"
                ),
                args_schema=SocialScanInput
            ),
        ])
    
    # Web reconnaissance tools
    if WEBRECON_AVAILABLE:
        web_recon = WebReconTools(agent)
        
        tool_list.extend([
            StructuredTool.from_function(
                func=web_recon.web_reconnaissance,
                name="osint_web_recon",
                description=(
                    "Comprehensive web reconnaissance of target URL. "
                    "Checks: headers, technologies, SSL, DNS, cookies, forms, links. "
                    "Analyzes security posture and technology stack. "
                    "Example: web_recon('https://example.com', checks=['headers', 'ssl'])"
                ),
                args_schema=WebReconInput
            ),
            
            StructuredTool.from_function(
                func=web_recon.playwright_scraper,
                name="osint_playwright_scrape",
                description=(
                    "Advanced web scraping with Playwright browser automation. "
                    "Handle JavaScript, execute code, extract data, bypass anti-bot. "
                    "Perfect for SPAs and dynamic content. "
                    "Example: playwright_scrape(url='https://example.com', selectors={'title': 'h1'})"
                ),
                args_schema=PlaywrightScraperInput
            ),
            
            StructuredTool.from_function(
                func=web_recon.fingerprint_technologies,
                name="osint_tech_fingerprint",
                description=(
                    "Advanced technology fingerprinting and stack detection. "
                    "Identifies web servers, frameworks, CMS, analytics, CDN. "
                    "Returns comprehensive technology analysis. "
                    "Example: tech_fingerprint('https://example.com')"
                ),
                args_schema=TechFingerprintInput
            ),
        ])
    
    return tool_list


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

"""
OSINT TOOLKIT USAGE EXAMPLES
=============================

1. CVE VULNERABILITY SEARCH:
   
   # Search for specific CVE
   osint_cve_search(query="CVE-2021-44228")
   
   # Search by product
   osint_cve_search(query="apache log4j", severity="CRITICAL", limit=20)
   
   # Filter by year
   osint_cve_search(query="wordpress", year=2024)


2. SUBDOMAIN ENUMERATION:
   
   # Passive enumeration (safe, uses certificate transparency)
   osint_subdomain_enum(domain="example.com", method="passive")
   
   # Bruteforce with common wordlist
   osint_subdomain_enum(domain="example.com", method="bruteforce", wordlist="common")
   
   # Hybrid approach
   osint_subdomain_enum(domain="example.com", method="hybrid", max_subdomains=200)


3. SOCIAL MEDIA SCANNING:
   
   # Scan all platforms
   osint_social_scan(username="johndoe")
   
   # Specific platforms only
   osint_social_scan(username="johndoe", platforms=["github", "twitter", "linkedin"])
   
   # Deep scan for more details
   osint_social_scan(username="johndoe", deep_scan=True)


4. WEB RECONNAISSANCE:
   
   # Full recon
   osint_web_recon(url="https://example.com")
   
   # Specific checks
   osint_web_recon(url="https://example.com", checks=["headers", "ssl", "technologies"])
   
   # With screenshot
   osint_web_recon(url="https://example.com", screenshot=True)


5. PLAYWRIGHT SCRAPING:
   
   # Extract specific elements
   osint_playwright_scrape(
       url="https://example.com",
       selectors={"title": "h1", "content": ".main-content", "links": "a"}
   )
   
   # Execute JavaScript
   osint_playwright_scrape(
       url="https://example.com",
       javascript="return document.title + ' - ' + window.location.href"
   )
   
   # Wait for dynamic content
   osint_playwright_scrape(
       url="https://example.com",
       wait_for=".dynamic-content",
       screenshot=True
   )


6. TECHNOLOGY FINGERPRINTING:
   
   # Full technology stack analysis
   osint_tech_fingerprint(url="https://example.com")
   
   # Specific detection methods
   osint_tech_fingerprint(
       url="https://example.com",
       methods=["headers", "scripts"]
   )


COMBINED RECONNAISSANCE WORKFLOW:
=================================

# Step 1: Gather basic information
web_info = osint_web_recon(url="https://target.com", checks=["headers", "ssl", "dns"])

# Step 2: Enumerate subdomains
subdomains = osint_subdomain_enum(domain="target.com", method="passive")

# Step 3: Fingerprint technologies
tech_stack = osint_tech_fingerprint(url="https://target.com")

# Step 4: Check for known vulnerabilities
# (Based on detected technologies from step 3)
cves = osint_cve_search(query="wordpress", severity="HIGH")

# Step 5: Social engineering research
# (Based on discovered information)
profiles = osint_social_scan(username="target_admin")

# Step 6: Deep content extraction
content = osint_playwright_scrape(
    url="https://target.com",
    selectors={"emails": "a[href^='mailto:']", "phones": "a[href^='tel:']"}
)


ETHICAL GUIDELINES:
===================

1. PERMISSION: Only scan targets you have explicit permission to test
2. RESPECT: Honor robots.txt and rate limits
3. PRIVACY: Don't collect or store personal information without consent
4. LEGAL: Comply with local laws and regulations (CFAA, GDPR, etc.)
5. RESPONSIBILITY: Report vulnerabilities responsibly through proper channels

These tools are for:
✓ Security research and testing on your own systems
✓ Bug bounty programs with proper authorization
✓ Competitive intelligence using public data
✓ Academic research with ethical approval

NOT for:
✗ Unauthorized access or testing
✗ Stalking or harassment
✗ Data theft or privacy violations
✗ Any illegal activities


INSTALLATION:
=============

Required packages:
    pip install dnspython python-whois requests beautifulsoup4
    pip install playwright
    playwright install chromium

Optional packages for extended features:
    pip install censys shodan builtwith pytz


DEPENDENCIES BY FEATURE:
========================

Core Features (always available):
- requests: HTTP requests
- beautifulsoup4: HTML parsing
- json, re: Built-in Python

DNS Features:
- dnspython: DNS resolution and queries

WHOIS Features:
- python-whois: Domain registration info

Browser Automation:
- playwright: Headless browser automation
"""


# ============================================================================
# CONFIGURATION
# ============================================================================

class OSINTConfig:
    """Configuration for OSINT tools."""
    
    # API Keys (optional, improves results)
    SHODAN_API_KEY = None
    CENSYS_API_ID = None
    CENSYS_API_SECRET = None
    VIRUSTOTAL_API_KEY = None
    
    # Rate limiting
    REQUEST_DELAY = 0.5  # Seconds between requests
    MAX_RETRIES = 3
    TIMEOUT = 10  # Request timeout in seconds
    
    # Output directories
    SCREENSHOT_DIR = "./Output/osint_screenshots"
    REPORT_DIR = "./Output/osint_reports"
    
    # Subdomain enumeration
    DEFAULT_WORDLIST = "common"
    MAX_SUBDOMAINS = 100
    DNS_TIMEOUT = 5
    
    # Browser automation
    HEADLESS = True
    BROWSER_TIMEOUT = 30000  # milliseconds
    
    # User agent
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_osint_report(results: dict, output_file: str = None) -> str:
    """
    Generate a formatted OSINT report from results.
    
    Args:
        results: Dictionary of OSINT tool results
        output_file: Optional file path to save report
    
    Returns: Formatted report as string
    """
    import json
    from datetime import datetime
    
    report = []
    report.append("=" * 80)
    report.append("OSINT RECONNAISSANCE REPORT")
    report.append("=" * 80)
    report.append(f"Generated: {datetime.now().isoformat()}")
    report.append("")
    
    # Add each section
    for tool_name, tool_results in results.items():
        report.append(f"\n{'='*80}")
        report.append(f"{tool_name.upper()}")
        report.append(f"{'='*80}")
        report.append(json.dumps(tool_results, indent=2))
    
    report_text = "\n".join(report)
    
    # Save to file if requested
    if output_file:
        with open(output_file, 'w') as f:
            f.write(report_text)
    
    return report_text


if __name__ == "__main__":
    print("OSINT Toolkit Integration")
    print("=" * 60)
    print("\nAvailable Tools:")
    print("  - osint_cve_search: CVE vulnerability search")
    print("  - osint_subdomain_enum: Subdomain enumeration")
    print("  - osint_social_scan: Social media profile scanning")
    print("  - osint_web_recon: Web reconnaissance")
    print("  - osint_playwright_scrape: Advanced web scraping")
    print("  - osint_tech_fingerprint: Technology fingerprinting")
    print("\nIntegration:")
    print("  from osint_integration import add_all_osint_tools")
    print("  add_all_osint_tools(tool_list, agent)")
    print("\nETHICAL USE ONLY - Get permission before scanning!")