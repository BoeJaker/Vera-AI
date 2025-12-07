"""
OSINT Tools - Part 2: Web Reconnaissance & Playwright
======================================================
Web intelligence gathering, automated browsing, and technology fingerprinting.
"""

import asyncio
import json
import re
import ssl
import socket
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse, urljoin
from pathlib import Path
import time

import requests
from bs4 import BeautifulSoup

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# Extend the OSINTTools class from part 1
class WebReconTools:
    """Web reconnaissance and browser automation tools."""
    
    def __init__(self, agent):
        self.agent = agent
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    # ------------------------------------------------------------------------
    # WEB RECONNAISSANCE
    # ------------------------------------------------------------------------
    
    def web_reconnaissance(self, url: str, checks: List[str] = None,
                          screenshot: bool = False) -> str:
        """
        Comprehensive web reconnaissance of a target URL.
        
        Performs multiple checks:
        - Headers: HTTP headers and security headers
        - Technologies: Detect frameworks, CMS, analytics
        - SSL: Certificate information and validation
        - DNS: DNS records and configuration
        - Cookies: Cookie analysis and flags
        - Forms: Form detection and attributes
        - Links: Internal/external link analysis
        
        Args:
            url: Target URL to analyze
            checks: Specific checks to perform (or None for all)
            screenshot: Capture screenshot of page
        
        Returns: Comprehensive reconnaissance report
        
        Example:
            web_reconnaissance("https://example.com")
            web_reconnaissance("https://example.com", checks=["headers", "ssl"])
        """
        try:
            if checks is None:
                checks = ["headers", "technologies", "ssl", "dns", "cookies", "forms", "links"]
            
            results = {
                "url": url,
                "timestamp": time.time(),
                "checks_performed": checks,
                "findings": {}
            }
            
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            
            # Headers Check
            if "headers" in checks:
                try:
                    response = self.session.get(url, timeout=10)
                    
                    headers_info = {
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "security_headers": {},
                        "missing_security_headers": []
                    }
                    
                    # Check for security headers
                    security_headers = {
                        "Strict-Transport-Security": "HSTS",
                        "Content-Security-Policy": "CSP",
                        "X-Frame-Options": "Clickjacking Protection",
                        "X-Content-Type-Options": "MIME Sniffing Protection",
                        "X-XSS-Protection": "XSS Protection",
                        "Referrer-Policy": "Referrer Policy",
                        "Permissions-Policy": "Permissions Policy"
                    }
                    
                    for header, description in security_headers.items():
                        if header in response.headers:
                            headers_info["security_headers"][header] = response.headers[header]
                        else:
                            headers_info["missing_security_headers"].append({
                                "header": header,
                                "description": description
                            })
                    
                    # Server fingerprint
                    if "Server" in response.headers:
                        headers_info["server"] = response.headers["Server"]
                    
                    # Powered by
                    if "X-Powered-By" in response.headers:
                        headers_info["powered_by"] = response.headers["X-Powered-By"]
                    
                    results["findings"]["headers"] = headers_info
                    
                except Exception as e:
                    results["findings"]["headers"] = {"error": str(e)}
            
            # Technology Detection
            if "technologies" in checks:
                try:
                    response = self.session.get(url, timeout=10)
                    
                    technologies = {
                        "detected": [],
                        "frameworks": [],
                        "cms": [],
                        "analytics": [],
                        "cdn": []
                    }
                    
                    html = response.text.lower()
                    
                    # Detect common technologies
                    tech_signatures = {
                        "wordpress": ["wp-content", "wp-includes"],
                        "drupal": ["drupal", "sites/all"],
                        "joomla": ["joomla", "com_content"],
                        "react": ["react", "__react"],
                        "vue": ["vue", "v-cloak"],
                        "angular": ["ng-", "angular"],
                        "jquery": ["jquery"],
                        "bootstrap": ["bootstrap"],
                        "tailwind": ["tailwind"],
                        "google_analytics": ["google-analytics", "gtag"],
                        "cloudflare": ["cloudflare"],
                        "nginx": ["nginx"],
                        "apache": ["apache"]
                    }
                    
                    for tech, signatures in tech_signatures.items():
                        if any(sig in html for sig in signatures):
                            technologies["detected"].append(tech)
                            
                            # Categorize
                            if tech in ["wordpress", "drupal", "joomla"]:
                                technologies["cms"].append(tech)
                            elif tech in ["react", "vue", "angular"]:
                                technologies["frameworks"].append(tech)
                            elif tech in ["google_analytics"]:
                                technologies["analytics"].append(tech)
                            elif tech in ["cloudflare"]:
                                technologies["cdn"].append(tech)
                    
                    # Check meta tags
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    meta_generator = soup.find("meta", {"name": "generator"})
                    if meta_generator and meta_generator.get("content"):
                        technologies["detected"].append(f"Generator: {meta_generator['content']}")
                    
                    results["findings"]["technologies"] = technologies
                    
                except Exception as e:
                    results["findings"]["technologies"] = {"error": str(e)}
            
            # SSL/TLS Check
            if "ssl" in checks and parsed_url.scheme == "https":
                try:
                    ssl_info = {
                        "valid": False,
                        "certificate": {},
                        "issues": []
                    }
                    
                    # Get SSL certificate
                    context = ssl.create_default_context()
                    
                    with socket.create_connection((domain, 443), timeout=10) as sock:
                        with context.wrap_socket(sock, server_hostname=domain) as ssock:
                            cert = ssock.getpeercert()
                            
                            ssl_info["valid"] = True
                            ssl_info["certificate"] = {
                                "subject": dict(x[0] for x in cert.get("subject", [])),
                                "issuer": dict(x[0] for x in cert.get("issuer", [])),
                                "version": cert.get("version"),
                                "serial_number": cert.get("serialNumber"),
                                "not_before": cert.get("notBefore"),
                                "not_after": cert.get("notAfter"),
                                "san": cert.get("subjectAltName", [])
                            }
                            
                            # Check expiry
                            from datetime import datetime
                            not_after = datetime.strptime(cert.get("notAfter"), "%b %d %H:%M:%S %Y %Z")
                            days_until_expiry = (not_after - datetime.now()).days
                            
                            if days_until_expiry < 30:
                                ssl_info["issues"].append(f"Certificate expires in {days_until_expiry} days")
                    
                    results["findings"]["ssl"] = ssl_info
                    
                except Exception as e:
                    results["findings"]["ssl"] = {"error": str(e), "valid": False}
            
            # DNS Check
            if "dns" in checks:
                try:
                    import dns.resolver
                    
                    dns_info = {
                        "records": {},
                        "nameservers": []
                    }
                    
                    resolver = dns.resolver.Resolver()
                    
                    # Query different record types
                    for record_type in ["A", "AAAA", "MX", "TXT", "NS"]:
                        try:
                            answers = resolver.resolve(domain, record_type)
                            dns_info["records"][record_type] = [str(rdata) for rdata in answers]
                        except:
                            pass
                    
                    results["findings"]["dns"] = dns_info
                    
                except Exception as e:
                    results["findings"]["dns"] = {"error": str(e)}
            
            # Cookies Check
            if "cookies" in checks:
                try:
                    response = self.session.get(url, timeout=10)
                    
                    cookies_info = {
                        "count": len(response.cookies),
                        "cookies": [],
                        "security_issues": []
                    }
                    
                    for cookie in response.cookies:
                        cookie_data = {
                            "name": cookie.name,
                            "domain": cookie.domain,
                            "path": cookie.path,
                            "secure": cookie.secure,
                            "httponly": cookie.has_nonstandard_attr("HttpOnly"),
                            "samesite": cookie.get_nonstandard_attr("SameSite")
                        }
                        
                        # Check for security issues
                        if not cookie.secure:
                            cookies_info["security_issues"].append(
                                f"Cookie '{cookie.name}' not marked as Secure"
                            )
                        
                        if not cookie.has_nonstandard_attr("HttpOnly"):
                            cookies_info["security_issues"].append(
                                f"Cookie '{cookie.name}' not marked as HttpOnly"
                            )
                        
                        cookies_info["cookies"].append(cookie_data)
                    
                    results["findings"]["cookies"] = cookies_info
                    
                except Exception as e:
                    results["findings"]["cookies"] = {"error": str(e)}
            
            # Forms Check
            if "forms" in checks:
                try:
                    response = self.session.get(url, timeout=10)
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    forms = soup.find_all("form")
                    
                    forms_info = {
                        "count": len(forms),
                        "forms": [],
                        "security_issues": []
                    }
                    
                    for form in forms:
                        form_data = {
                            "action": form.get("action", ""),
                            "method": form.get("method", "GET").upper(),
                            "inputs": []
                        }
                        
                        # Get input fields
                        inputs = form.find_all(["input", "textarea", "select"])
                        for inp in inputs:
                            form_data["inputs"].append({
                                "type": inp.get("type", "text"),
                                "name": inp.get("name", ""),
                                "id": inp.get("id", "")
                            })
                        
                        # Check for security issues
                        if form_data["method"] == "GET":
                            # Check for password fields in GET forms
                            if any(inp.get("type") == "password" for inp in form.find_all("input")):
                                forms_info["security_issues"].append(
                                    "Password field in GET form (should use POST)"
                                )
                        
                        forms_info["forms"].append(form_data)
                    
                    results["findings"]["forms"] = forms_info
                    
                except Exception as e:
                    results["findings"]["forms"] = {"error": str(e)}
            
            # Links Analysis
            if "links" in checks:
                try:
                    response = self.session.get(url, timeout=10)
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    links = soup.find_all("a", href=True)
                    
                    links_info = {
                        "total": len(links),
                        "internal": 0,
                        "external": 0,
                        "external_domains": set(),
                        "suspicious": []
                    }
                    
                    for link in links:
                        href = link.get("href", "")
                        
                        # Parse link
                        if href.startswith("http"):
                            link_domain = urlparse(href).netloc
                            
                            if link_domain == domain:
                                links_info["internal"] += 1
                            else:
                                links_info["external"] += 1
                                links_info["external_domains"].add(link_domain)
                        elif href.startswith("/"):
                            links_info["internal"] += 1
                        
                        # Check for suspicious patterns
                        if any(pattern in href.lower() for pattern in ["javascript:", "data:", "vbscript:"]):
                            links_info["suspicious"].append(href[:100])
                    
                    links_info["external_domains"] = list(links_info["external_domains"])
                    
                    results["findings"]["links"] = links_info
                    
                except Exception as e:
                    results["findings"]["links"] = {"error": str(e)}
            
            # Screenshot
            if screenshot and PLAYWRIGHT_AVAILABLE:
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                screenshot_path = loop.run_until_complete(
                    self._capture_screenshot(url)
                )
                
                if screenshot_path:
                    results["screenshot"] = screenshot_path
            
            # Store in agent memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                f"Web recon: {url}",
                "osint_web_recon",
                metadata={"url": url, "checks": checks}
            )
            
            return json.dumps(results, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "url": url
            })
    
    async def _capture_screenshot(self, url: str) -> Optional[str]:
        """Capture screenshot using Playwright."""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                await page.goto(url, wait_until="networkidle", timeout=30000)
                
                # Generate filename
                timestamp = int(time.time())
                filename = f"screenshot_{hashlib.md5(url.encode()).hexdigest()[:8]}_{timestamp}.png"
                output_path = Path("./Output/osint_screenshots")
                output_path.mkdir(parents=True, exist_ok=True)
                
                screenshot_path = output_path / filename
                await page.screenshot(path=str(screenshot_path), full_page=True)
                
                await browser.close()
                
                return str(screenshot_path)
        except Exception as e:
            print(f"Screenshot error: {e}")
            return None
    
    # ------------------------------------------------------------------------
    # PLAYWRIGHT WEB SCRAPING
    # ------------------------------------------------------------------------
    
    def playwright_scraper(self, url: str, selectors: Optional[Dict[str, str]] = None,
                          javascript: Optional[str] = None, wait_for: Optional[str] = None,
                          screenshot: bool = False) -> str:
        """
        Advanced web scraping using Playwright browser automation.
        
        Capabilities:
        - Execute JavaScript on page
        - Wait for dynamic content
        - Extract data using CSS selectors
        - Handle SPAs and AJAX-heavy sites
        - Capture screenshots
        - Bypass basic anti-bot measures
        
        Args:
            url: URL to scrape
            selectors: CSS selectors to extract: {"name": "selector"}
            javascript: JavaScript code to execute on page
            wait_for: CSS selector to wait for before scraping
            screenshot: Capture screenshot
        
        Returns: Extracted data, screenshot path, and page metadata
        
        Example:
            playwright_scraper(
                url="https://example.com",
                selectors={"title": "h1", "content": ".main-content"},
                wait_for=".main-content"
            )
        """
        try:
            if not PLAYWRIGHT_AVAILABLE:
                return json.dumps({
                    "error": "Playwright not available - install with: pip install playwright && playwright install"
                })
            
            # Setup event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Run async scraping
            result = loop.run_until_complete(
                self._async_playwright_scrape(url, selectors, javascript, wait_for, screenshot)
            )
            
            # Store in agent memory
            if result.get("success"):
                self.agent.mem.add_session_memory(
                    self.agent.sess.id,
                    f"Playwright scrape: {url}",
                    "osint_playwright",
                    metadata={"url": url, "selectors": list(selectors.keys()) if selectors else []}
                )
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "url": url
            })
    
    async def _async_playwright_scrape(self, url: str, selectors: Optional[Dict[str, str]],
                                       javascript: Optional[str], wait_for: Optional[str],
                                       screenshot: bool) -> Dict[str, Any]:
        """Async Playwright scraping implementation."""
        result = {
            "url": url,
            "success": False,
            "data": {},
            "metadata": {}
        }
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled']
                )
                
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    viewport={'width': 1920, 'height': 1080}
                )
                
                # Add stealth
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)
                
                page = await context.new_page()
                
                # Navigate
                response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                
                result["metadata"]["status"] = response.status
                result["metadata"]["final_url"] = page.url
                
                # Wait for selector if specified
                if wait_for:
                    try:
                        await page.wait_for_selector(wait_for, timeout=10000)
                    except PlaywrightTimeout:
                        result["warnings"] = [f"Timeout waiting for selector: {wait_for}"]
                
                # Execute JavaScript if provided
                if javascript:
                    try:
                        js_result = await page.evaluate(javascript)
                        result["data"]["javascript_result"] = js_result
                    except Exception as e:
                        result["data"]["javascript_error"] = str(e)
                
                # Extract data using selectors
                if selectors:
                    for name, selector in selectors.items():
                        try:
                            elements = await page.query_selector_all(selector)
                            
                            extracted = []
                            for elem in elements:
                                text = await elem.inner_text()
                                extracted.append(text.strip())
                            
                            result["data"][name] = extracted
                        except Exception as e:
                            result["data"][f"{name}_error"] = str(e)
                
                # Get page title and meta
                result["metadata"]["title"] = await page.title()
                
                # Capture screenshot if requested
                if screenshot:
                    timestamp = int(time.time())
                    filename = f"playwright_{hashlib.md5(url.encode()).hexdigest()[:8]}_{timestamp}.png"
                    output_path = Path("./Output/osint_screenshots")
                    output_path.mkdir(parents=True, exist_ok=True)
                    
                    screenshot_path = output_path / filename
                    await page.screenshot(path=str(screenshot_path))
                    result["screenshot"] = str(screenshot_path)
                
                await browser.close()
                
                result["success"] = True
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    # ------------------------------------------------------------------------
    # TECHNOLOGY FINGERPRINTING
    # ------------------------------------------------------------------------
    
    def fingerprint_technologies(self, url: str, methods: List[str] = None) -> str:
        """
        Advanced technology fingerprinting and detection.
        
        Detection methods:
        - Headers: Server headers and HTTP fingerprints
        - HTML: HTML structure and patterns
        - Scripts: JavaScript libraries and frameworks
        - Meta: Meta tags and generators
        
        Detects:
        - Web servers (Apache, Nginx, IIS, etc.)
        - Programming languages (PHP, Python, Ruby, etc.)
        - Frameworks (Django, Laravel, Express, etc.)
        - CMS (WordPress, Drupal, Joomla, etc.)
        - JavaScript frameworks (React, Vue, Angular, etc.)
        - Analytics and tracking
        - CDNs and hosting
        
        Returns: Comprehensive technology stack analysis
        """
        try:
            if methods is None:
                methods = ["headers", "html", "scripts", "meta"]
            
            results = {
                "url": url,
                "methods": methods,
                "technologies": {
                    "web_server": [],
                    "backend": [],
                    "frontend": [],
                    "cms": [],
                    "analytics": [],
                    "cdn": [],
                    "hosting": [],
                    "other": []
                },
                "confidence": {}
            }
            
            response = self.session.get(url, timeout=10)
            
            # Header-based detection
            if "headers" in methods:
                headers = response.headers
                
                # Web server
                if "Server" in headers:
                    server = headers["Server"]
                    results["technologies"]["web_server"].append(server)
                    results["confidence"]["web_server"] = "high"
                
                # Backend language
                if "X-Powered-By" in headers:
                    powered_by = headers["X-Powered-By"]
                    results["technologies"]["backend"].append(powered_by)
                    results["confidence"]["backend"] = "high"
                
                # Framework hints
                framework_headers = {
                    "X-AspNet-Version": "ASP.NET",
                    "X-AspNetMvc-Version": "ASP.NET MVC",
                    "X-Django-Version": "Django",
                    "X-Rails-Version": "Ruby on Rails"
                }
                
                for header, framework in framework_headers.items():
                    if header in headers:
                        results["technologies"]["backend"].append(
                            f"{framework} {headers[header]}"
                        )
            
            # HTML-based detection
            if "html" in methods:
                html = response.text
                soup = BeautifulSoup(html, 'html.parser')
                
                # Meta generator
                meta_gen = soup.find("meta", {"name": "generator"})
                if meta_gen and meta_gen.get("content"):
                    gen = meta_gen["content"]
                    results["technologies"]["cms"].append(gen)
                    results["confidence"]["cms"] = "high"
                
                # WordPress
                if "wp-content" in html or "wp-includes" in html:
                    results["technologies"]["cms"].append("WordPress")
                    results["confidence"]["cms"] = "high"
                    
                    # Try to detect version
                    version_match = re.search(r'wp-includes/js/.*?ver=([0-9.]+)', html)
                    if version_match:
                        results["technologies"]["cms"][0] = f"WordPress {version_match.group(1)}"
                
                # Other CMS detection
                cms_patterns = {
                    "Drupal": ["drupal", "sites/all"],
                    "Joomla": ["joomla", "com_content"],
                    "Magento": ["magento", "mage/cookies"],
                    "Shopify": ["shopify", "cdn.shopify"],
                    "Wix": ["wix.com", "parastorage"]
                }
                
                for cms, patterns in cms_patterns.items():
                    if any(p in html.lower() for p in patterns):
                        if cms not in results["technologies"]["cms"]:
                            results["technologies"]["cms"].append(cms)
            
            # Script-based detection
            if "scripts" in methods:
                soup = BeautifulSoup(response.text, 'html.parser')
                scripts = soup.find_all("script", src=True)
                
                script_urls = [script.get("src", "") for script in scripts]
                all_scripts = " ".join(script_urls).lower()
                
                # JavaScript frameworks
                js_frameworks = {
                    "React": ["react", "react-dom"],
                    "Vue.js": ["vue.js", "vue.min"],
                    "Angular": ["angular", "ng-"],
                    "jQuery": ["jquery"],
                    "Ember.js": ["ember"],
                    "Backbone.js": ["backbone"],
                    "Next.js": ["_next/"],
                    "Nuxt.js": ["_nuxt/"]
                }
                
                for framework, patterns in js_frameworks.items():
                    if any(p in all_scripts for p in patterns):
                        results["technologies"]["frontend"].append(framework)
                
                # Analytics
                analytics_patterns = {
                    "Google Analytics": ["google-analytics", "gtag", "ga.js"],
                    "Google Tag Manager": ["googletagmanager"],
                    "Facebook Pixel": ["facebook", "fbevents"],
                    "Hotjar": ["hotjar"],
                    "Mixpanel": ["mixpanel"]
                }
                
                for tool, patterns in analytics_patterns.items():
                    if any(p in all_scripts for p in patterns):
                        results["technologies"]["analytics"].append(tool)
                
                # CDN detection
                cdn_patterns = {
                    "Cloudflare": ["cloudflare"],
                    "Fastly": ["fastly"],
                    "Akamai": ["akamai"],
                    "CloudFront": ["cloudfront"],
                    "jsDelivr": ["jsdelivr"],
                    "unpkg": ["unpkg.com"]
                }
                
                for cdn, patterns in cdn_patterns.items():
                    if any(p in all_scripts for p in patterns):
                        results["technologies"]["cdn"].append(cdn)
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                f"Tech fingerprint: {url}",
                "osint_fingerprint",
                metadata={"url": url, "technologies_found": sum(len(v) for v in results["technologies"].values())}
            )
            
            return json.dumps(results, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "url": url
            })


# ============================================================================
# TOOL LOADER
# ============================================================================

def add_web_recon_tools(tool_list: List, agent):
    """Add web reconnaissance and Playwright tools."""
    from langchain_core.tools import StructuredTool
    from osint_tools_core import (
        WebReconInput, PlaywrightScraperInput, TechFingerprintInput
    )
    
    web_tools = WebReconTools(agent)
    
    tool_list.extend([
        StructuredTool.from_function(
            func=web_tools.web_reconnaissance,
            name="web_recon",
            description=(
                "Comprehensive web reconnaissance: headers, technologies, SSL, DNS, cookies, forms, links. "
                "Analyze security posture and technology stack of target website."
            ),
            args_schema=WebReconInput
        ),
        
        StructuredTool.from_function(
            func=web_tools.playwright_scraper,
            name="playwright_scrape",
            description=(
                "Advanced web scraping with Playwright browser automation. "
                "Handle JavaScript-heavy sites, execute code, extract data, bypass anti-bot. "
                "Perfect for SPAs and dynamic content."
            ),
            args_schema=PlaywrightScraperInput
        ),
        
        StructuredTool.from_function(
            func=web_tools.fingerprint_technologies,
            name="tech_fingerprint",
            description=(
                "Advanced technology fingerprinting and stack detection. "
                "Identify web servers, frameworks, CMS, analytics, CDN, and more."
            ),
            args_schema=TechFingerprintInput
        ),
    ])
    
    return tool_list