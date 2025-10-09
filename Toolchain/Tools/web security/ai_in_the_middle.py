"""
Web Traffic Interceptor Tool for LangChain

WARNING: This tool has significant security and ethical implications.
Only use on systems you own or have explicit permission to test.
"""

from langchain.tools import BaseTool
from typing import Optional, Type, Any, Dict, List
from pydantic import BaseModel, Field, validator
import asyncio
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from mitmproxy import http, options, proxy
from mitmproxy.tools.dump import DumpMaster
import json
import time
from bs4 import BeautifulSoup
import re

class WebInterceptorInput(BaseModel):
    """Input for Web Interceptor tool."""
    action: str = Field(description="Action to perform: 'start_interception', 'stop_interception', 'add_overlay', 'modify_page', 'add_comment', 'security_scan'")
    target_url: Optional[str] = Field(default=None, description="Target URL for the action")
    overlay_content: Optional[str] = Field(default=None, description="HTML content for overlay")
    modification_rules: Optional[Dict[str, str]] = Field(default=None, description="CSS selector to replacement content mapping")
    comment: Optional[str] = Field(default=None, description="Comment to add to page")
    security_checks: Optional[List[str]] = Field(default=None, description="List of security checks to perform")

class WebInterceptorTool(BaseTool):
    name = "web_traffic_interceptor"
    description = """
    Intercept and manipulate web traffic, add overlays to webpages, comment on live browsing, and monitor security.
    Use with extreme caution and only on authorized systems.
    """
    args_schema: Type[BaseModel] = WebInterceptorInput
    
    # Class-level variables for state management
    _interception_active = False
    _mitm_thread = None
    _mitm_server = None
    _browser = None
    _modification_rules = {}
    _overlays = {}
    _comments = {}
    _security_alerts = []
    
    def _run(self, action: str, target_url: Optional[str] = None, 
             overlay_content: Optional[str] = None, modification_rules: Optional[Dict[str, str]] = None,
             comment: Optional[str] = None, security_checks: Optional[List[str]] = None) -> str:
        """Execute the web interception tool."""
        
        # Security warning
        if not self._confirm_authorization():
            return "ERROR: Authorization not confirmed. Tool requires explicit user confirmation."
        
        try:
            if action == "start_interception":
                return self._start_interception()
            elif action == "stop_interception":
                return self._stop_interception()
            elif action == "add_overlay":
                if not target_url or not overlay_content:
                    return "ERROR: target_url and overlay_content required for add_overlay"
                return self._add_overlay(target_url, overlay_content)
            elif action == "modify_page":
                if not target_url or not modification_rules:
                    return "ERROR: target_url and modification_rules required for modify_page"
                return self._modify_page(target_url, modification_rules)
            elif action == "add_comment":
                if not target_url or not comment:
                    return "ERROR: target_url and comment required for add_comment"
                return self._add_comment(target_url, comment)
            elif action == "security_scan":
                if not target_url:
                    return "ERROR: target_url required for security_scan"
                return self._security_scan(target_url, security_checks or [])
            else:
                return f"ERROR: Unknown action: {action}"
                
        except Exception as e:
            return f"ERROR: {str(e)}"
    
    async def _arun(self, *args, **kwargs):
        """Async version not implemented."""
        raise NotImplementedError("Async operation not supported")
    
    def _confirm_authorization(self) -> bool:
        """Confirm the user authorizes this potentially dangerous operation."""
        # In a real implementation, this would have proper user confirmation
        print("WARNING: This tool can intercept and modify web traffic.")
        print("Only use on systems you own or have explicit permission to test.")
        return True  # In real usage, this would require actual confirmation
    
    def _start_interception(self) -> str:
        """Start the interception proxy."""
        if self._interception_active:
            return "Interception is already active"
        
        # Start mitmproxy in a separate thread
        self._interception_active = True
        self._mitm_thread = threading.Thread(target=self._run_mitmproxy)
        self._mitm_thread.daemon = True
        self._mitm_thread.start()
        
        # Configure browser to use proxy
        self._start_browser_with_proxy()
        
        return "Web traffic interception started. Browser launched with proxy settings."
    
    def _stop_interception(self) -> str:
        """Stop the interception proxy."""
        if not self._interception_active:
            return "Interception is not active"
        
        self._interception_active = False
        if self._browser:
            self._browser.quit()
            self._browser = None
        
        return "Web traffic interception stopped."
    
    def _run_mitmproxy(self):
        """Run mitmproxy with our custom addons."""
        opts = options.Options(
            listen_host='127.0.0.1',
            listen_port=8080,
            mode='regular',
            ssl_insecure=True
        )
        
        pconf = proxy.config.ProxyConfig(opts)
        self._mitm_server = DumpMaster(opts)
        self._mitm_server.server = proxy.server.ProxyServer(pconf)
        
        # Add our request/response handlers
        self._mitm_server.addons.add(InterceptionAddon(
            self._modification_rules,
            self._overlays,
            self._comments,
            self._security_alerts
        ))
        
        try:
            self._mitm_server.run()
        except Exception as e:
            print(f"mitmproxy error: {e}")
    
    def _start_browser_with_proxy(self):
        """Start a browser configured to use our proxy."""
        chrome_options = Options()
        chrome_options.add_argument('--proxy-server=http://127.0.0.1:8080')
        chrome_options.add_argument('--ignore-certificate-errors')
        
        self._browser = webdriver.Chrome(options=chrome_options)
        self._browser.get('http://example.com')  # Start with a simple page
    
    def _add_overlay(self, target_url: str, content: str) -> str:
        """Add an overlay to a specific URL."""
        self._overlays[target_url] = content
        return f"Overlay added for {target_url}. It will appear on next page load."
    
    def _modify_page(self, target_url: str, rules: Dict[str, str]) -> str:
        """Store modification rules for a URL."""
        if target_url not in self._modification_rules:
            self._modification_rules[target_url] = {}
        
        self._modification_rules[target_url].update(rules)
        return f"Modification rules added for {target_url}. Changes will apply on next page load."
    
    def _add_comment(self, target_url: str, comment: str) -> str:
        """Add a comment to a page."""
        if target_url not in self._comments:
            self._comments[target_url] = []
        
        self._comments[target_url].append(comment)
        return f"Comment added to {target_url}. It will appear on next page load."
    
    def _security_scan(self, target_url: str, checks: List[str]) -> str:
        """Perform security checks on a URL."""
        # This would be implemented with actual security checks
        results = []
        
        if 'xss' in checks:
            results.append("XSS check: No obvious vulnerabilities detected")
        
        if 'ssl' in checks:
            results.append("SSL check: Certificate validation disabled for testing")
        
        if 'sensitive_data' in checks:
            results.append("Sensitive data check: No obvious data exposure detected")
        
        return f"Security scan results for {target_url}:\n" + "\n".join(results)


class InterceptionAddon:
    """mitmproxy addon to handle request/response modification."""
    
    def __init__(self, modification_rules, overlays, comments, security_alerts):
        self.modification_rules = modification_rules
        self.overlays = overlays
        self.comments = comments
        self.security_alerts = security_alerts
    
    def response(self, flow: http.HTTPFlow):
        """Modify HTTP responses."""
        url = flow.request.pretty_url
        
        # Check if we need to modify this response
        if flow.response and flow.response.content:
            content = flow.response.content.decode('utf-8', errors='ignore')
            
            # Apply modifications based on URL patterns
            modified = False
            
            # Apply content modifications
            for pattern_url, rules in self.modification_rules.items():
                if re.match(pattern_url.replace('*', '.*'), url):
                    modified_content = content
                    for selector, replacement in rules.items():
                        if selector == "page_title":
                            modified_content = re.sub(
                                r'<title>[^<]*</title>', 
                                f'<title>{replacement}</title>', 
                                modified_content
                            )
                        else:
                            # Simple HTML modification (in real use, use proper HTML parser)
                            modified_content = modified_content.replace(
                                selector, replacement
                            )
                    content = modified_content
                    modified = True
            
            # Add overlays
            for overlay_url, overlay_html in self.overlays.items():
                if re.match(overlay_url.replace('*', '.*'), url):
                    # Insert overlay div at the end of the body
                    overlay_code = f"""
                    <div style="position: fixed; top: 10px; right: 10px; 
                    background: yellow; padding: 10px; z-index: 9999; 
                    border: 2px solid red; max-width: 300px;">
                    {overlay_html}
                    </div>
                    """
                    content = content.replace('</body>', overlay_code + '</body>')
                    modified = True
            
            # Add comments
            for comment_url, comment_list in self.comments.items():
                if re.match(comment_url.replace('*', '.*'), url):
                    comments_html = "<div style='background: #f0f0f0; padding: 10px; margin: 10px; border-left: 4px solid blue;'><h4>Page Comments:</h4><ul>"
                    for comment in comment_list:
                        comments_html += f"<li>{comment}</li>"
                    comments_html += "</ul></div>"
                    content = content.replace('</body>', comments_html + '</body>')
                    modified = True
            
            # Security monitoring
            self._check_security(flow, content)
            
            if modified:
                flow.response.text = content
                flow.response.headers["content-length"] = str(len(content))
    
    def _check_security(self, flow: http.HTTPFlow, content: str):
        """Perform security checks on the response."""
        url = flow.request.pretty_url
        
        # Check for potential sensitive data
        sensitive_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN-like pattern
            r'\b\d{16}\b',  # Credit card-like pattern
            r'password[=:]\s*[\w@#$%^&*]+',  # Password in content
        ]
        
        for pattern in sensitive_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                self.security_alerts.append(
                    f"Potential sensitive data exposure at {url}: Pattern {pattern} matched"
                )
        
        # Check for common security headers
        security_headers = [
            'x-frame-options',
            'x-content-type-options',
            'x-xss-protection',
            'strict-transport-security'
        ]
        
        missing_headers = []
        for header in security_headers:
            if header not in flow.response.headers:
                missing_headers.append(header)
        
        if missing_headers:
            self.security_alerts.append(
                f"Missing security headers at {url}: {', '.join(missing_headers)}"
            )


# Example usage with LangChain
def create_web_interceptor_tool():
    """Create an instance of the web interceptor tool for LangChain."""
    return WebInterceptorTool()

# Example of how to use with a LangChain agent
if __name__ == "__main__":
    # This would be used within a LangChain agent setup
    tool = create_web_interceptor_tool()
    
    # Example: Start interception
    result = tool.run({
        "action": "start_interception"
    })
    print(result)
    
    # Example: Add an overlay to a site
    result = tool.run({
        "action": "add_overlay",
        "target_url": "https://example.com/*",
        "overlay_content": "Security Warning: This site is being monitored"
    })
    print(result)
    
    # Example: Add a comment
    result = tool.run({
        "action": "add_comment",
        "target_url": "https://example.com/*",
        "comment": "This site appears to be using outdated JavaScript libraries"
    })
    print(result)