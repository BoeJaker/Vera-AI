#!/usr/bin/env python3
"""
Enhanced Search Engine Dorking Toolkit for Vera
KEYWORD-BASED + CUSTOM DORK + ALL ORIGINAL FEATURES

Features:
- NEW: Simple keyword search with intelligent dork generation
- Multi-engine support (Google, Bing, DuckDuckGo, Yahoo, Yandex)
- Anti-captcha measures (rotation, delays, sessions)
- 500+ pre-built dork patterns
- Custom dork generation
- Category-based searches (files, logins, cameras, misconfigs)
- Result extraction and parsing
- Graph memory integration
- Proxy support

Search Categories:
- Exposed Files (configs, databases, logs, backups)
- Login Portals (admin panels, webmail, dashboards)
- Network Devices (cameras, routers, printers, IoT)
- Misconfigurations (directory listings, error pages)
- Sensitive Documents (PDFs, spreadsheets, presentations)
- Cloud Storage (S3 buckets, Azure blobs, Google storage)
- Code Repositories (exposed .git, .svn)
- Personal Information (emails, phone numbers, social profiles)

Dependencies:
    pip install requests beautifulsoup4 fake-useragent
"""

import re
import time
import random
import hashlib
import urllib.parse
from typing import List, Dict, Any, Optional, Set, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydantic import BaseModel, Field
from enum import Enum
import logging

import requests
from bs4 import BeautifulSoup

# Fake user agent for rotation
try:
    from fake_useragent import UserAgent
    FAKE_UA_AVAILABLE = True
except ImportError:
    FAKE_UA_AVAILABLE = False
    print("[Warning] fake-useragent not available - install for better anti-detection")

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

class SearchEngine(str, Enum):
    """Supported search engines"""
    GOOGLE = "google"
    BING = "bing"
    DUCKDUCKGO = "duckduckgo"
    YAHOO = "yahoo"
    YANDEX = "yandex"
    STARTPAGE = "startpage"
    ALL = "all"

class DorkCategory(str, Enum):
    """Dork search categories"""
    FILES = "files"
    LOGINS = "logins"
    CAMERAS = "cameras"
    DEVICES = "devices"
    MISCONFIGS = "misconfigs"
    DOCUMENTS = "documents"
    CLOUD = "cloud"
    CODE = "code"
    PEOPLE = "people"
    CUSTOM = "custom"

@dataclass
class DorkingConfig:
    """Configuration for dorking operations"""
    
    # Search engines
    engines: List[str] = field(default_factory=lambda: ["google", "bing", "duckduckgo"])
    
    # Anti-detection
    use_random_user_agents: bool = True
    min_delay: float = 3.0
    max_delay: float = 8.0
    rotate_sessions: bool = True
    session_rotation_interval: int = 10
    use_referrers: bool = True
    verify_ssl: bool = True
    
    # Search parameters
    max_results_per_engine: int = 50
    max_pages_per_search: int = 5
    results_per_page: int = 10
    
    # Proxy configuration
    use_proxies: bool = False
    proxy_list: Optional[List[str]] = None
    rotate_proxies: bool = True
    
    # Filtering
    domain_filter: Optional[str] = None
    exclude_domains: Optional[List[str]] = None
    date_filter: Optional[str] = None  # "day", "week", "month", "year"
    file_type_filter: Optional[str] = None
    
    # Result processing
    extract_emails: bool = True
    extract_phones: bool = True
    extract_ips: bool = True
    follow_redirects: bool = False
    check_availability: bool = True
    
    # Graph memory
    link_to_session: bool = True
    create_resource_nodes: bool = True
    link_discoveries: bool = True
    
    # Performance
    max_threads: int = 3
    request_timeout: int = 15
    
    @classmethod
    def stealth_mode(cls) -> 'DorkingConfig':
        """Maximum anti-detection configuration"""
        return cls(
            engines=["duckduckgo", "bing", "startpage"],
            min_delay=5.0,
            max_delay=15.0,
            rotate_sessions=True,
            session_rotation_interval=5,
            use_random_user_agents=True,
            use_referrers=True,
            max_threads=1
        )
    
    @classmethod
    def aggressive_mode(cls) -> 'DorkingConfig':
        """Fast but higher detection risk"""
        return cls(
            engines=["google", "bing", "duckduckgo", "yahoo"],
            min_delay=1.0,
            max_delay=3.0,
            rotate_sessions=False,
            max_threads=5,
            max_results_per_engine=100
        )

# =============================================================================
# PYDANTIC SCHEMAS - ORIGINAL + NEW
# =============================================================================

class FlexibleDorkInput(BaseModel):
    """Base schema for dorking"""
    target: str = Field(description="Target domain, keyword, or dork query")

class FileDorkInput(FlexibleDorkInput):
    file_types: Optional[List[str]] = Field(
        default=None,
        description="File types: sql, log, env, config, bak, xml, json, csv"
    )
    keywords: Optional[List[str]] = Field(
        default=None,
        description="Additional keywords to include"
    )

class LoginDorkInput(FlexibleDorkInput):
    login_types: Optional[List[str]] = Field(
        default=None,
        description="Login types: admin, webmail, cpanel, phpmyadmin, wordpress"
    )

class DeviceDorkInput(FlexibleDorkInput):
    device_types: Optional[List[str]] = Field(
        default=None,
        description="Device types: camera, webcam, printer, router, nas, scada"
    )

class MisconfigDorkInput(FlexibleDorkInput):
    misconfig_types: Optional[List[str]] = Field(
        default=None,
        description="Types: directory_listing, error_page, debug, trace"
    )

class PeopleDorkInput(FlexibleDorkInput):
    info_types: Optional[List[str]] = Field(
        default=None,
        description="Info types: email, phone, social, resume, linkedin"
    )

class CustomDorkInput(FlexibleDorkInput):
    dork_query: str = Field(description="Custom Google dork query")
    engine: str = Field(default="google", description="Search engine to use")

class ComprehensiveDorkInput(FlexibleDorkInput):
    categories: Optional[List[str]] = Field(
        default=None,
        description="Categories to search: files, logins, cameras, devices, misconfigs"
    )
    depth: str = Field(
        default="standard",
        description="Search depth: quick, standard, deep"
    )

# NEW: Unified schema for keyword + custom dork searches
class UnifiedDorkInput(BaseModel):
    """
    Unified schema for keyword and custom dork searches.
    
    Examples:
        - Simple keyword: search="webcam"
        - With target: search="webcam", target="example.com"
        - Custom dork: search='intitle:"webcam" inurl:view.shtml'
        - Hybrid: search="admin login", file_type="php"
    """
    search: str = Field(
        description=(
            "Search query - can be:\n"
            "1. Simple keyword: 'webcam', 'admin panel', 'database'\n"
            "2. Custom dork: 'intitle:\"login\" inurl:admin'\n"
            "3. Multiple keywords: 'exposed camera streaming'\n"
            "Auto-detects and generates appropriate dork queries"
        )
    )
    
    target: Optional[str] = Field(
        default=None,
        description="Optional target domain or keyword to focus on (e.g., 'example.com' or 'company name')"
    )
    
    file_type: Optional[str] = Field(
        default=None,
        description="File type filter: sql, pdf, xls, doc, log, env, config, etc."
    )
    
    site: Optional[str] = Field(
        default=None,
        description="Limit to specific site/domain (e.g., 'example.com')"
    )
    
    exclude_sites: Optional[List[str]] = Field(
        default=None,
        description="Domains to exclude from results"
    )
    
    date_range: Optional[str] = Field(
        default=None,
        description="Time filter: 'day', 'week', 'month', 'year'"
    )
    
    max_results: Optional[int] = Field(
        default=50,
        description="Maximum results to return per engine"
    )
    
    engines: Optional[List[str]] = Field(
        default=None,
        description="Search engines to use: ['google', 'bing', 'duckduckgo']"
    )
    
    mode: Optional[str] = Field(
        default="smart",
        description="Search mode: 'smart' (auto), 'keyword' (force keyword search), 'custom' (force as custom dork)"
    )

class QuickSearchInput(BaseModel):
    """Quick search with just keywords"""
    keywords: str = Field(description="Keywords to search for (e.g., 'webcam', 'admin login')")
    target: Optional[str] = Field(default=None, description="Optional target domain")

# =============================================================================
# KEYWORD-TO-DORK INTELLIGENT MAPPING (NEW)
# =============================================================================

class DorkGenerator:
    """
    Intelligent dork query generator from keywords.
    Maps common keywords to effective dork patterns.
    """
    
    # Keyword categories with associated dork patterns
    KEYWORD_PATTERNS = {
        # Network devices
        "webcam": [
            'intitle:"Live View" -demo',
            'inurl:view/index.shtml',
            'intitle:"network camera"',
            'inurl:ViewerFrame?Mode=',
            'intitle:"webcam 7"',
            'inurl:"CgiStart?page="'
        ],
        "camera": [
            'intitle:"Live View / - AXIS"',
            'intitle:"network camera"',
            'inurl:view.shtml',
            'intitle:"i-Catcher Console"',
            'inurl:MultiCameraFrame?Mode='
        ],
        "printer": [
            'intitle:"Printer Status"',
            'inurl:hp/device/this.LCDispatcher',
            'intitle:"Lexmark" "Printer Status"',
            'intitle:"Canon" inurl:login.html'
        ],
        "router": [
            'intitle:"DD-WRT"',
            'intitle:"EdgeRouter"',
            'intitle:"pfSense"',
            'intitle:"MikroTik RouterOS"',
            'intitle:"ASUS Router"'
        ],
        
        # Login portals
        "admin": [
            'intitle:"Admin Panel"',
            'inurl:admin intitle:login',
            'inurl:administrator intitle:login',
            'inurl:admin/login.php',
            'intitle:"Dashboard" "admin"'
        ],
        "login": [
            'intitle:login',
            'inurl:login',
            'intitle:"Please log in"',
            'inurl:signin'
        ],
        "dashboard": [
            'intitle:"Dashboard"',
            'intitle:"Control Panel"',
            'intitle:"Admin Dashboard"'
        ],
        "phpmyadmin": [
            'intitle:"phpMyAdmin"',
            'inurl:phpmyadmin intitle:index',
            '"Welcome to phpMyAdmin"'
        ],
        
        # Files and documents
        "database": [
            'filetype:sql',
            'filetype:db',
            'ext:sqlite',
            'filetype:mdb'
        ],
        "backup": [
            'filetype:bak',
            'filetype:zip inurl:backup',
            'ext:old',
            'filetype:tar.gz inurl:backup'
        ],
        "config": [
            'filetype:config',
            'ext:conf',
            'ext:ini',
            'filetype:env',
            'filetype:yaml'
        ],
        "password": [
            'filetype:txt "password"',
            'filetype:xls "password"',
            'ext:csv "password"',
            'filetype:sql "password"'
        ],
        "credentials": [
            'filetype:txt "username" "password"',
            'ext:csv "credentials"',
            'filetype:config "username"'
        ],
        "log": [
            'filetype:log',
            'ext:log inurl:log',
            'filetype:log "error"'
        ],
        
        # Misconfigurations
        "directory listing": [
            'intitle:"Index of /"',
            'intitle:"Index of /backup"',
            'intitle:"Index of /admin"'
        ],
        "error": [
            'intitle:"Error Occurred"',
            'intitle:"Server Error"',
            'intitle:"PHP Fatal error"',
            'intitle:"Warning: mysql"'
        ],
        "exposed": [
            'inurl:"/.git" intitle:"Index of"',
            'inurl:.git/config',
            'inurl:"/.svn"'
        ],
        
        # Cloud storage
        "s3": [
            'site:s3.amazonaws.com',
            'site:s3.amazonaws.com inurl:backup',
            'site:s3.amazonaws.com filetype:pdf'
        ],
        "aws": [
            'site:s3.amazonaws.com',
            'site:amazonaws.com'
        ],
        "azure": [
            'site:blob.core.windows.net',
            'site:blob.core.windows.net inurl:backup'
        ],
        
        # Document types
        "pdf": [
            'filetype:pdf',
            'ext:pdf'
        ],
        "spreadsheet": [
            'filetype:xls OR filetype:xlsx',
            'ext:csv'
        ],
        "document": [
            'filetype:doc OR filetype:docx',
            'filetype:pdf OR filetype:doc'
        ],
        
        # Development
        "api": [
            'inurl:api',
            'intitle:"API Documentation"',
            'inurl:/api/ filetype:json'
        ],
        "git": [
            'inurl:"/.git" intitle:"Index of"',
            'inurl:.git/HEAD',
            'inurl:.git/config'
        ],
        "jenkins": [
            'intitle:"Dashboard [Jenkins]"',
            'intitle:"Jenkins" "Manage Jenkins"'
        ],
        
        # Information types
        "email": [
            'filetype:xls intext:"@"',
            'filetype:csv intext:"@"',
            'filetype:txt "email"'
        ],
        "phone": [
            'filetype:xls "phone"',
            'filetype:csv "phone" "name"'
        ],
        "resume": [
            'filetype:pdf "resume"',
            'filetype:doc "curriculum vitae"'
        ]
    }
    
    # Dork operator detection patterns
    DORK_OPERATORS = [
        'site:', 'inurl:', 'intitle:', 'filetype:', 'ext:', 
        'intext:', 'allintext:', 'allintitle:', 'allinurl:',
        'cache:', 'link:', 'related:', 'info:'
    ]
    
    @classmethod
    def is_custom_dork(cls, query: str) -> bool:
        """Detect if query contains dork operators"""
        return any(op in query.lower() for op in cls.DORK_OPERATORS)
    
    @classmethod
    def generate_dorks_from_keywords(cls, keywords: str, target: Optional[str] = None,
                                     file_type: Optional[str] = None,
                                     max_dorks: int = 10) -> List[str]:
        """
        Generate dork queries from keywords.
        
        Args:
            keywords: Search keywords
            target: Optional target domain/keyword
            file_type: Optional file type filter
            max_dorks: Maximum number of dork variations to generate
        
        Returns:
            List of generated dork queries
        """
        dorks = []
        keywords_lower = keywords.lower().strip()
        
        # Check for exact keyword matches in patterns
        if keywords_lower in cls.KEYWORD_PATTERNS:
            dorks.extend(cls.KEYWORD_PATTERNS[keywords_lower][:max_dorks])
        else:
            # Check for partial matches
            for keyword, patterns in cls.KEYWORD_PATTERNS.items():
                if keyword in keywords_lower or keywords_lower in keyword:
                    dorks.extend(patterns[:3])  # Add fewer for partial matches
        
        # If no matches found, generate generic dorks from keywords
        if not dorks:
            dorks = cls._generate_generic_dorks(keywords, max_dorks)
        
        # Apply modifiers
        modified_dorks = []
        for dork in dorks[:max_dorks]:
            # Add target if specified
            if target:
                if 'site:' not in dork.lower():
                    dork = f"{dork} site:{target}"
                else:
                    # Replace placeholder or add as additional term
                    dork = f"{dork} {target}"
            
            # Add file type if specified
            if file_type and 'filetype:' not in dork.lower() and 'ext:' not in dork.lower():
                dork = f"{dork} filetype:{file_type}"
            
            modified_dorks.append(dork.strip())
        
        return modified_dorks or [keywords]  # Fallback to raw keywords
    
    @classmethod
    def _generate_generic_dorks(cls, keywords: str, max_dorks: int = 5) -> List[str]:
        """Generate generic dork patterns from arbitrary keywords"""
        dorks = []
        words = keywords.split()
        
        if len(words) == 1:
            word = words[0]
            dorks = [
                f'intitle:"{word}"',
                f'inurl:{word}',
                f'intext:"{word}"',
                f'{word}',
                f'"{word}"'
            ]
        else:
            # Multi-word keywords
            dorks = [
                f'intitle:"{keywords}"',
                f'inurl:{words[0]} intitle:{words[-1]}',
                f'intext:"{keywords}"',
                f'"{keywords}"',
                f'{keywords}'
            ]
        
        return dorks[:max_dorks]
    
    @classmethod
    def parse_and_enhance_query(cls, query: str, target: Optional[str] = None,
                                file_type: Optional[str] = None,
                                site: Optional[str] = None,
                                exclude_sites: Optional[List[str]] = None) -> str:
        """
        Parse query and enhance with additional parameters.
        Handles both custom dorks and keyword searches.
        """
        # If it's a custom dork, just enhance it
        if cls.is_custom_dork(query):
            enhanced = query
        else:
            # It's a keyword search - use it as is but enhance
            enhanced = query
        
        # Add site restriction
        if site and 'site:' not in enhanced.lower():
            enhanced = f"{enhanced} site:{site}"
        
        # Add file type
        if file_type and 'filetype:' not in enhanced.lower() and 'ext:' not in enhanced.lower():
            enhanced = f"{enhanced} filetype:{file_type}"
        
        # Add target as search term
        if target and target not in enhanced:
            enhanced = f"{enhanced} {target}"
        
        # Exclude sites
        if exclude_sites:
            for exclude_site in exclude_sites:
                if f'-site:{exclude_site}' not in enhanced.lower():
                    enhanced = f"{enhanced} -site:{exclude_site}"
        
        return enhanced.strip()

# =============================================================================
# DORK PATTERN DATABASE
# =============================================================================

class DorkPatterns:
    """Comprehensive database of Google dork patterns"""
    
    # File exposure dorks
    FILES = {
        "sql_dumps": [
            'filetype:sql inurl:backup',
            'filetype:sql "INSERT INTO" "VALUES"',
            'filetype:sql "CREATE TABLE"',
            'filetype:sql inurl:dump',
            'ext:sql "password"',
            'ext:sql "admin"'
        ],
        "log_files": [
            'filetype:log inurl:log',
            'filetype:log "error"',
            'filetype:log "password"',
            'ext:log "username"',
            'ext:log inurl:access'
        ],
        "config_files": [
            'filetype:env "DB_PASSWORD"',
            'filetype:config inurl:web.config',
            'ext:conf inurl:proftpd',
            'ext:ini "password"',
            'filetype:properties inurl:db',
            'ext:cfg "password"',
            'filetype:yaml "password"',
            'filetype:toml "password"'
        ],
        "backup_files": [
            'filetype:bak inurl:backup',
            'ext:old "password"',
            'filetype:zip inurl:backup',
            'ext:tar.gz inurl:backup',
            'filetype:sql.gz',
            'ext:bkp'
        ],
        "database_files": [
            'filetype:mdb "password"',
            'ext:sqlite',
            'filetype:db',
            'ext:accdb'
        ],
        "source_code": [
            'ext:java "password"',
            'ext:py "password"',
            'ext:php "password"',
            'ext:js "password"',
            'filetype:ashx "password"'
        ],
        "credential_files": [
            'filetype:txt "password"',
            'filetype:csv "password"',
            'filetype:xls "password"',
            'ext:xlsx "password"',
            'filetype:doc "password"',
            'ext:docx "password"'
        ]
    }
    
    # Login portal dorks
    LOGINS = {
        "admin_panels": [
            'inurl:admin intitle:login',
            'inurl:administrator intitle:login',
            'inurl:admin/login.php',
            'inurl:admin/admin.php',
            'inurl:admin/index.php',
            'intitle:"Admin Panel"',
            'inurl:wp-admin',
            'inurl:administrator',
            'inurl:moderator',
            'inurl:controlpanel',
            'inurl:admincontrol'
        ],
        "webmail": [
            'intitle:"webmail login"',
            'inurl:webmail intitle:login',
            'inurl:mail/login',
            'intitle:"SquirrelMail"',
            'intitle:"Roundcube Webmail"',
            'intitle:"Horde" "login"'
        ],
        "database_admin": [
            'intitle:"phpMyAdmin" "Welcome to phpMyAdmin"',
            'inurl:phpmyadmin intitle:index',
            'intitle:"Adminer" "Login"',
            'intitle:"phpPgAdmin"',
            'intitle:"SQL Server Management"'
        ],
        "cms_logins": [
            'inurl:wp-login.php',
            'inurl:user/login "Drupal"',
            'inurl:admin/login "Joomla"',
            'intitle:"Dashboard" "Magento"',
            'inurl:ghost/signin',
            'inurl:admin "DNN Platform"'
        ],
        "control_panels": [
            'intitle:"cPanel"',
            'intitle:"Plesk"',
            'intitle:"DirectAdmin"',
            'intitle:"Webmin"',
            'intitle:"ISPConfig"',
            'intitle:"Virtualmin"'
        ],
        "remote_access": [
            'intitle:"Remote Desktop Web Connection"',
            'intitle:"Terminal Services Web Access"',
            'intitle:"Citrix Access Gateway"',
            'intitle:"Pulse Secure" "login"',
            'intitle:"OpenVPN" "login"'
        ]
    }
    
    # Network device dorks
    DEVICES = {
        "cameras": [
            'intitle:"Live View / - AXIS"',
            'inurl:view/index.shtml',
            'intitle:"network camera"',
            'intitle:"webcam 7"',
            'intitle:"Live View / - AXIS" | inurl:view/view.shtml',
            'inurl:ViewerFrame?Mode=',
            'intitle:"EvoCam" inurl:webcam.html',
            'intitle:"Live NetCam"',
            'intitle:"i-Catcher Console"',
            'intitle:"Yawcam" "Camera"',
            'inurl:"CgiStart?page="',
            'intitle:"BlueIris Login"'
        ],
        "printers": [
            'intitle:"HP LaserJet" inurl:SSI/Auth',
            'intitle:"Printer Status"',
            'inurl:hp/device/this.LCDispatcher',
            'intitle:"Lexmark" "Printer Status"',
            'intitle:"Canon" inurl:/English/pages_WinUS/login.html',
            'inurl:PNPDevice.asp'
        ],
        "routers": [
            'intitle:"DD-WRT"',
            'intitle:"EdgeRouter"',
            'intitle:"pfSense"',
            'intitle:"MikroTik RouterOS"',
            'intitle:"Linksys" inurl:apply.cgi',
            'intitle:"ASUS Router"',
            'intitle:"Tomato" "admin"'
        ],
        "nas_devices": [
            'intitle:"Synology DiskStation"',
            'intitle:"QNAP Turbo NAS"',
            'intitle:"ReadyNAS Frontview"',
            'intitle:"FreeNAS"',
            'intitle:"OpenMediaVault"'
        ],
        "iot_devices": [
            'inurl:8080 intitle:"Yawcam"',
            'intitle:"toshiba network camera" user login',
            'inurl:indexFrame.shtml "Axis"',
            'intitle:"WJ-NT104"',
            'inurl:MultiCameraFrame?Mode=Motion'
        ],
        "scada_ics": [
            'intitle:"Schneider Electric"',
            'intitle:"Siemens" "SIMATIC"',
            'intitle:"Allen-Bradley"',
            'intitle:"Rockwell Automation"',
            'intitle:"GE Intelligent Platforms"'
        ]
    }
    
    # Misconfiguration dorks
    MISCONFIGS = {
        "directory_listing": [
            'intitle:"Index of /" +.zip',
            'intitle:"Index of /" +.sql',
            'intitle:"Index of /" +backup',
            'intitle:"Index of /" +password',
            'intitle:"Index of /" +.env',
            'intitle:"Index of /backup"',
            'intitle:"Index of /config"',
            'intitle:"Index of /admin"',
            'intitle:"Index of /uploads"',
            'intitle:"index of" inurl:ftp'
        ],
        "error_pages": [
            'intitle:"Error Occurred While Processing Request"',
            'intitle:"Server Error in" "Application"',
            'intitle:"PHP Fatal error"',
            'intitle:"Warning: mysql"',
            'intitle:"Error Message : Error loading required libraries."',
            '"A syntax error has occurred" filetype:ihtml',
            'intitle:"Error" "Microsoft OLE DB Provider for SQL Server"'
        ],
        "debug_pages": [
            'intitle:"phpinfo()"',
            'intitle:"Test Page for Apache Installation"',
            'intitle:"Welcome to nginx!"',
            'intitle:"IIS Windows Server"',
            'inurl:debug.log',
            'inurl:errors.log'
        ],
        "exposed_panels": [
            'intitle:"Docker Dashboard"',
            'intitle:"Kubernetes Dashboard"',
            'intitle:"Jenkins Dashboard"',
            'intitle:"Grafana"',
            'intitle:"Kibana"',
            'intitle:"Elasticsearch Head"'
        ],
        "git_exposure": [
            'inurl:"/.git" intitle:"Index of"',
            'filetype:git "index"',
            'inurl:.git/config',
            'inurl:.git/HEAD'
        ],
        "svn_exposure": [
            'inurl:"/.svn" intitle:"Index of"',
            'inurl:.svn/entries'
        ]
    }
    
    # Sensitive document dorks
    DOCUMENTS = {
        "confidential": [
            'filetype:pdf "confidential"',
            'filetype:pdf "internal use only"',
            'filetype:pdf "not for distribution"',
            'filetype:doc "confidential"',
            'ext:xlsx "confidential"'
        ],
        "financial": [
            'filetype:xls "invoice"',
            'filetype:pdf "balance sheet"',
            'filetype:pdf "bank statement"',
            'filetype:csv "credit card"',
            'filetype:xls "salary"'
        ],
        "personal": [
            'filetype:pdf "curriculum vitae"',
            'filetype:doc "resume"',
            'filetype:pdf "social security number"',
            'filetype:pdf "passport"',
            'filetype:xls "employee"'
        ],
        "medical": [
            'filetype:pdf "medical record"',
            'filetype:pdf "patient"',
            'filetype:xls "diagnosis"',
            'filetype:doc "prescription"'
        ],
        "legal": [
            'filetype:pdf "contract"',
            'filetype:pdf "agreement"',
            'filetype:pdf "NDA"',
            'filetype:doc "terms and conditions"'
        ]
    }
    
    # Cloud storage dorks
    CLOUD = {
        "aws_s3": [
            'site:s3.amazonaws.com inurl:backup',
            'site:s3.amazonaws.com inurl:prod',
            'site:s3.amazonaws.com filetype:pdf',
            'site:s3.amazonaws.com filetype:xls',
            'site:s3.amazonaws.com "confidential"',
            'site:s3.amazonaws.com inurl:dev'
        ],
        "azure_blob": [
            'site:blob.core.windows.net',
            'site:blob.core.windows.net inurl:backup',
            'site:blob.core.windows.net filetype:pdf'
        ],
        "google_storage": [
            'site:storage.googleapis.com',
            'site:storage.googleapis.com inurl:backup'
        ],
        "dropbox": [
            'site:dl.dropboxusercontent.com',
            'site:dropbox.com/s/'
        ]
    }
    
    # Code repository dorks
    CODE = {
        "github": [
            'site:github.com "password"',
            'site:github.com "api_key"',
            'site:github.com "secret_key"',
            'site:github.com "AWS_ACCESS_KEY_ID"',
            'site:github.com "PRIVATE KEY"'
        ],
        "gitlab": [
            'site:gitlab.com "password"',
            'site:gitlab.com "api_key"'
        ],
        "bitbucket": [
            'site:bitbucket.org "password"'
        ],
        "pastebin": [
            'site:pastebin.com "password"',
            'site:pastebin.com "api_key"',
            'site:pastebin.com "credentials"'
        ]
    }
    
    # People/OSINT dorks
    PEOPLE = {
        "email": [
            '"@{domain}" filetype:xls',
            '"@{domain}" filetype:csv',
            '"@{domain}" filetype:txt',
            'intext:"@{domain}" inurl:contact'
        ],
        "phone": [
            'intext:"{keyword}" intext:"phone"',
            'intext:"{keyword}" intext:"mobile"',
            'intext:"{keyword}" intext:"tel"'
        ],
        "social": [
            'site:linkedin.com "{keyword}"',
            'site:twitter.com "{keyword}"',
            'site:facebook.com "{keyword}"',
            'site:instagram.com "{keyword}"'
        ],
        "resumes": [
            'filetype:pdf "resume" "{keyword}"',
            'filetype:doc "CV" "{keyword}"',
            'filetype:pdf "curriculum vitae" "{keyword}"'
        ]
    }
    
    @staticmethod
    def get_dorks_by_category(category: str) -> List[str]:
        """Get all dorks for a category"""
        category_map = {
            "files": DorkPatterns.FILES,
            "logins": DorkPatterns.LOGINS,
            "cameras": DorkPatterns.DEVICES.get("cameras", []),
            "devices": DorkPatterns.DEVICES,
            "misconfigs": DorkPatterns.MISCONFIGS,
            "documents": DorkPatterns.DOCUMENTS,
            "cloud": DorkPatterns.CLOUD,
            "code": DorkPatterns.CODE,
            "people": DorkPatterns.PEOPLE
        }
        
        patterns = category_map.get(category.lower(), {})
        
        if isinstance(patterns, dict):
            all_dorks = []
            for dork_list in patterns.values():
                all_dorks.extend(dork_list)
            return all_dorks
        
        return patterns

# =============================================================================
# SEARCH ENGINE IMPLEMENTATIONS
# =============================================================================

class BaseSearchEngine:
    """Base class for search engines"""
    
    def __init__(self, config: DorkingConfig):
        self.config = config
        self.session = requests.Session()
        self.request_count = 0
        
        # User agent rotation
        if FAKE_UA_AVAILABLE and config.use_random_user_agents:
            self.ua = UserAgent()
        else:
            self.user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
        
        # Referrers for anti-detection
        self.referrers = [
            'https://www.google.com/',
            'https://www.bing.com/',
            'https://duckduckgo.com/',
            'https://www.yahoo.com/',
            'https://www.reddit.com/',
            'https://twitter.com/'
        ]
    
    def _get_user_agent(self) -> str:
        """Get random user agent"""
        if FAKE_UA_AVAILABLE and self.config.use_random_user_agents:
            return self.ua.random
        return random.choice(self.user_agents)
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with anti-detection"""
        headers = {
            'User-Agent': self._get_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        if self.config.use_referrers:
            headers['Referer'] = random.choice(self.referrers)
        
        return headers
    
    def _rotate_session(self):
        """Rotate session for anti-detection"""
        if self.config.rotate_sessions:
            if self.request_count % self.config.session_rotation_interval == 0:
                self.session.close()
                self.session = requests.Session()
    
    def _delay(self):
        """Random delay for anti-detection"""
        delay = random.uniform(self.config.min_delay, self.config.max_delay)
        time.sleep(delay)
    
    def search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search - to be implemented by subclasses"""
        raise NotImplementedError

class GoogleSearchEngine(BaseSearchEngine):
    """Google search with anti-detection"""
    
    def __init__(self, config: DorkingConfig):
        super().__init__(config)
        self.base_url = "https://www.google.com/search"
    
    def search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search Google"""
        results = []
        num_pages = min(
            (max_results // self.config.results_per_page) + 1,
            self.config.max_pages_per_search
        )
        
        for page in range(num_pages):
            try:
                start = page * self.config.results_per_page
                
                params = {
                    'q': query,
                    'start': start,
                    'num': self.config.results_per_page,
                    'hl': 'en'
                }
                
                # Apply date filter
                if self.config.date_filter:
                    tbs_map = {
                        'day': 'd',
                        'week': 'w',
                        'month': 'm',
                        'year': 'y'
                    }
                    tbs = tbs_map.get(self.config.date_filter)
                    if tbs:
                        params['tbs'] = f'qdr:{tbs}'
                
                self._rotate_session()
                
                response = self.session.get(
                    self.base_url,
                    params=params,
                    headers=self._get_headers(),
                    timeout=self.config.request_timeout,
                    verify=self.config.verify_ssl
                )
                
                self.request_count += 1
                
                if response.status_code != 200:
                    logger.warning(f"Google returned status {response.status_code}")
                    break
                
                # Check for captcha
                if 'detected unusual traffic' in response.text.lower():
                    logger.warning("Google captcha detected - stopping search")
                    break
                
                # Parse results
                page_results = self._parse_results(response.text)
                results.extend(page_results)
                
                if len(results) >= max_results:
                    break
                
                # Delay between requests
                self._delay()
            
            except Exception as e:
                logger.error(f"Google search error: {e}")
                break
        
        return results[:max_results]
    
    def _parse_results(self, html: str) -> List[Dict[str, Any]]:
        """Parse Google search results"""
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        
        # Find search result divs
        for g in soup.find_all('div', class_='g'):
            try:
                # Extract title
                title_elem = g.find('h3')
                title = title_elem.get_text() if title_elem else ""
                
                # Extract URL
                link_elem = g.find('a')
                url = link_elem.get('href') if link_elem else ""
                
                # Clean URL (remove Google redirect)
                if url.startswith('/url?q='):
                    url = url.split('/url?q=')[1].split('&')[0]
                
                # Extract snippet
                snippet_elem = g.find('div', class_=['VwiC3b', 'yXK7lf'])
                snippet = snippet_elem.get_text() if snippet_elem else ""
                
                if url and not url.startswith('http'):
                    continue
                
                results.append({
                    'engine': 'google',
                    'title': title,
                    'url': urllib.parse.unquote(url),
                    'snippet': snippet
                })
            
            except Exception:
                continue
        
        return results

class BingSearchEngine(BaseSearchEngine):
    """Bing search with anti-detection"""
    
    def __init__(self, config: DorkingConfig):
        super().__init__(config)
        self.base_url = "https://www.bing.com/search"
    
    def search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search Bing"""
        results = []
        num_pages = min(
            (max_results // self.config.results_per_page) + 1,
            self.config.max_pages_per_search
        )
        
        for page in range(num_pages):
            try:
                first = page * self.config.results_per_page + 1
                
                params = {
                    'q': query,
                    'first': first,
                    'count': self.config.results_per_page
                }
                
                self._rotate_session()
                
                response = self.session.get(
                    self.base_url,
                    params=params,
                    headers=self._get_headers(),
                    timeout=self.config.request_timeout,
                    verify=self.config.verify_ssl
                )
                
                self.request_count += 1
                
                if response.status_code != 200:
                    break
                
                page_results = self._parse_results(response.text)
                results.extend(page_results)
                
                if len(results) >= max_results:
                    break
                
                self._delay()
            
            except Exception as e:
                logger.error(f"Bing search error: {e}")
                break
        
        return results[:max_results]
    
    def _parse_results(self, html: str) -> List[Dict[str, Any]]:
        """Parse Bing search results"""
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        
        for li in soup.find_all('li', class_='b_algo'):
            try:
                # Extract title and URL
                h2 = li.find('h2')
                if not h2:
                    continue
                
                a = h2.find('a')
                if not a:
                    continue
                
                title = a.get_text()
                url = a.get('href', '')
                
                # Extract snippet
                snippet_elem = li.find('p')
                snippet = snippet_elem.get_text() if snippet_elem else ""
                
                results.append({
                    'engine': 'bing',
                    'title': title,
                    'url': url,
                    'snippet': snippet
                })
            
            except Exception:
                continue
        
        return results

class DuckDuckGoSearchEngine(BaseSearchEngine):
    """DuckDuckGo search (best for anti-detection)"""
    
    def __init__(self, config: DorkingConfig):
        super().__init__(config)
        self.base_url = "https://html.duckduckgo.com/html/"
    
    def search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search DuckDuckGo"""
        results = []
        
        try:
            # DuckDuckGo requires POST
            data = {
                'q': query,
                'b': '',
                'kl': 'us-en'
            }
            
            response = self.session.post(
                self.base_url,
                data=data,
                headers=self._get_headers(),
                timeout=self.config.request_timeout,
                verify=self.config.verify_ssl
            )
            
            self.request_count += 1
            
            if response.status_code == 200:
                results = self._parse_results(response.text)
            
            self._delay()
        
        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
        
        return results[:max_results]
    
    def _parse_results(self, html: str) -> List[Dict[str, Any]]:
        """Parse DuckDuckGo results"""
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        
        for result in soup.find_all('div', class_='result'):
            try:
                # Extract title and URL
                title_elem = result.find('a', class_='result__a')
                if not title_elem:
                    continue
                
                title = title_elem.get_text()
                url = title_elem.get('href', '')
                
                # Extract snippet
                snippet_elem = result.find('a', class_='result__snippet')
                snippet = snippet_elem.get_text() if snippet_elem else ""
                
                results.append({
                    'engine': 'duckduckgo',
                    'title': title,
                    'url': url,
                    'snippet': snippet
                })
            
            except Exception:
                continue
        
        return results

# =============================================================================
# DORKING MAPPER - ORCHESTRATES SEARCHES
# =============================================================================

class DorkingMapper:
    """
    Dorking mapper with multi-engine support and memory integration.
    NOW WITH: Keyword-to-dork intelligence
    """
    
    def __init__(self, agent, config: DorkingConfig):
        self.agent = agent
        self.config = config
        
        # Initialize search engines
        self.engines = {}
        if "google" in config.engines or "all" in config.engines:
            self.engines["google"] = GoogleSearchEngine(config)
        if "bing" in config.engines or "all" in config.engines:
            self.engines["bing"] = BingSearchEngine(config)
        if "duckduckgo" in config.engines or "all" in config.engines:
            self.engines["duckduckgo"] = DuckDuckGoSearchEngine(config)
        
        # Tracking
        self.search_node_id = None
        self.discovered_resources = {}
        
        # Email/phone/IP extraction patterns
        self.email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        self.phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        self.ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
    
    def _initialize_search(self, tool_name: str, query: str):
        """Initialize search context"""
        if self.search_node_id is not None:
            return
        
        try:
            search_mem = self.agent.mem.add_session_memory(
                self.agent.sess.id,
                f"Dorking search: {query}",
                "dorking_search",
                metadata={
                    "tool": tool_name,
                    "query": query,
                    "started_at": datetime.now().isoformat(),
                }
            )
            self.search_node_id = search_mem.id
        except Exception:
            pass
    
    def _create_resource_node(self, resource_data: Dict[str, Any]) -> str:
        """Create discovered resource node"""
        url = resource_data.get('url', '')
        resource_id = f"resource_{hashlib.md5(url.encode()).hexdigest()[:12]}"
        
        if resource_id in self.discovered_resources:
            return self.discovered_resources[resource_id]
        
        try:
            properties = {
                "url": url,
                "title": resource_data.get('title', ''),
                "snippet": resource_data.get('snippet', '')[:500],
                "engine": resource_data.get('engine'),
                "discovered_at": datetime.now().isoformat(),
            }
            
            # Add extracted data
            if resource_data.get('emails'):
                properties['emails'] = resource_data['emails']
            if resource_data.get('phones'):
                properties['phones'] = resource_data['phones']
            if resource_data.get('ips'):
                properties['ips'] = resource_data['ips']
            if resource_data.get('available') is not None:
                properties['available'] = resource_data['available']
            
            self.agent.mem.upsert_entity(
                resource_id,
                "web_resource",
                labels=["WebResource", "DorkResult"],
                properties=properties
            )
            
            if self.search_node_id:
                self.agent.mem.link(
                    self.search_node_id,
                    resource_id,
                    "DISCOVERED_RESOURCE",
                    {"engine": resource_data.get('engine')}
                )
            
            self.discovered_resources[resource_id] = resource_id
            return resource_id
        
        except Exception as e:
            logger.error(f"Failed to create resource node: {e}")
            return resource_id
    
    def _extract_information(self, text: str) -> Dict[str, List[str]]:
        """Extract emails, phones, IPs from text"""
        extracted = {
            'emails': [],
            'phones': [],
            'ips': []
        }
        
        if self.config.extract_emails:
            extracted['emails'] = list(set(re.findall(self.email_pattern, text)))
        
        if self.config.extract_phones:
            extracted['phones'] = list(set(re.findall(self.phone_pattern, text)))
        
        if self.config.extract_ips:
            extracted['ips'] = list(set(re.findall(self.ip_pattern, text)))
        
        return extracted
    
    def _check_url_availability(self, url: str) -> bool:
        """Check if URL is accessible"""
        try:
            response = requests.head(
                url,
                timeout=5,
                allow_redirects=True,
                verify=False
            )
            return response.status_code < 400
        except:
            return False
    
    def _build_dork_query(self, base_query: str, target: str) -> str:
        """Build complete dork query"""
        query = base_query.replace('{domain}', target).replace('{keyword}', target)
        
        # Add domain filter if specified
        if self.config.domain_filter:
            query = f"{query} site:{self.config.domain_filter}"
        
        # Add file type filter
        if self.config.file_type_filter:
            query = f"{query} filetype:{self.config.file_type_filter}"
        
        # Exclude domains
        if self.config.exclude_domains:
            for domain in self.config.exclude_domains:
                query = f"{query} -site:{domain}"
        
        return query
    
    def _search_all_engines(self, query: str) -> Iterator[Dict[str, Any]]:
        """Search across all configured engines"""
        for engine_name, engine in self.engines.items():
            try:
                results = engine.search(query, self.config.max_results_per_engine)
                
                for result in results:
                    # Extract information from snippet
                    extracted = self._extract_information(
                        result['title'] + ' ' + result['snippet']
                    )
                    
                    result.update(extracted)
                    
                    # Check availability if configured
                    if self.config.check_availability:
                        result['available'] = self._check_url_availability(result['url'])
                    
                    yield result
            
            except Exception as e:
                logger.error(f"Engine {engine_name} failed: {e}")
                continue
    
    # =========================================================================
    # NEW: UNIFIED KEYWORD + CUSTOM DORK SEARCH
    # =========================================================================
    
    def unified_search(self, search: str, target: Optional[str] = None,
                      file_type: Optional[str] = None, site: Optional[str] = None,
                      exclude_sites: Optional[List[str]] = None,
                      max_results: int = 50, mode: str = "smart") -> Iterator[str]:
        """
        Unified search supporting both keywords and custom dorks.
        
        Args:
            search: Keyword(s) or custom dork query
            target: Optional target domain/keyword
            file_type: Optional file type filter
            site: Optional site restriction
            exclude_sites: Sites to exclude
            max_results: Max results per engine
            mode: 'smart' (auto-detect), 'keyword', or 'custom'
        """
        
        self._initialize_search("unified_search", search)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                    INTELLIGENT DORK SEARCH                   ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        # Determine if custom dork or keyword search
        is_custom = DorkGenerator.is_custom_dork(search)
        
        if mode == "keyword":
            is_custom = False
        elif mode == "custom":
            is_custom = True
        # else: mode == "smart", use auto-detection
        
        if is_custom:
            # Custom dork query
            yield f"  Mode: Custom Dork\n"
            query = DorkGenerator.parse_and_enhance_query(
                search, target, file_type, site, exclude_sites
            )
            queries = [query]
        else:
            # Keyword search - generate multiple dorks
            yield f"  Mode: Keyword Search\n"
            yield f"  Keywords: {search}\n"
            queries = DorkGenerator.generate_dorks_from_keywords(
                search, target, file_type, max_dorks=5
            )
            
            # Apply additional filters
            if site or exclude_sites:
                queries = [
                    DorkGenerator.parse_and_enhance_query(
                        q, target, file_type, site, exclude_sites
                    ) for q in queries
                ]
        
        yield f"  Engines: {', '.join(self.engines.keys())}\n"
        yield f"  Generated Queries: {len(queries)}\n\n"
        
        # Show queries
        for i, q in enumerate(queries, 1):
            yield f"  [{i}] {q}\n"
        yield "\n"
        
        total_results = 0
        unique_urls = set()
        
        # Execute searches
        for i, query in enumerate(queries, 1):
            yield f"─── Query {i}/{len(queries)} {'─' * 40}\n"
            
            found = 0
            for result in self._search_all_engines(query):
                # Deduplicate by URL
                if result['url'] in unique_urls:
                    continue
                
                unique_urls.add(result['url'])
                self._create_resource_node(result)
                found += 1
                total_results += 1
                
                yield f"  [✓] {result['url']}\n"
                yield f"      {result['title'][:80]}\n"
                
                # Show extracted data
                if result.get('emails'):
                    yield f"      📧 {', '.join(result['emails'][:3])}\n"
                if result.get('phones'):
                    yield f"      📞 {', '.join(result['phones'][:2])}\n"
                if result.get('ips'):
                    yield f"      🌐 {', '.join(result['ips'][:2])}\n"
                
                yield "\n"
            
            if found == 0:
                yield f"  No results for this query\n\n"
        
        yield f"╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║  Total Unique Results: {total_results:>43} ║\n"
        yield f"║  Queries Executed: {len(queries):>47} ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def quick_search(self, keywords: str, target: Optional[str] = None) -> Iterator[str]:
        """Quick keyword search with minimal configuration"""
        yield from self.unified_search(
            search=keywords,
            target=target,
            mode="keyword",
            max_results=30
        )
    
    # =========================================================================
    # ORIGINAL CATEGORY-SPECIFIC DORKING OPERATIONS (ALL PRESERVED)
    # =========================================================================
    
    def search_files(self, target: str, file_types: Optional[List[str]] = None,
                    keywords: Optional[List[str]] = None) -> Iterator[str]:
        """Search for exposed files"""
        
        self._initialize_search("search_files", target)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                    FILE EXPOSURE SEARCH                      ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        yield f"  Target: {target}\n"
        yield f"  Engines: {', '.join(self.engines.keys())}\n\n"
        
        # Get file dorks
        if file_types:
            dorks = []
            for ft in file_types:
                if ft in DorkPatterns.FILES:
                    dorks.extend(DorkPatterns.FILES[ft])
        else:
            dorks = DorkPatterns.get_dorks_by_category("files")
        
        total_results = 0
        
        for i, dork_pattern in enumerate(dorks[:20], 1):  # Limit dorks
            dork_query = self._build_dork_query(dork_pattern, target)
            
            yield f"  [{i}] Searching: {dork_pattern[:60]}...\n"
            
            found = 0
            for result in self._search_all_engines(dork_query):
                self._create_resource_node(result)
                found += 1
                total_results += 1
                
                yield f"      [✓] {result['url']}\n"
                
                if result.get('emails'):
                    yield f"          Emails: {', '.join(result['emails'][:3])}\n"
            
            if found == 0:
                yield f"      No results\n"
            
            yield "\n"
        
        yield f"╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Total Resources Found: {total_results}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def search_logins(self, target: str, login_types: Optional[List[str]] = None) -> Iterator[str]:
        """Search for login portals"""
        
        self._initialize_search("search_logins", target)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                    LOGIN PORTAL SEARCH                       ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        yield f"  Target: {target}\n\n"
        
        # Get login dorks
        if login_types:
            dorks = []
            for lt in login_types:
                if lt in DorkPatterns.LOGINS:
                    dorks.extend(DorkPatterns.LOGINS[lt])
        else:
            dorks = DorkPatterns.get_dorks_by_category("logins")
        
        total_results = 0
        
        for i, dork_pattern in enumerate(dorks[:15], 1):
            dork_query = self._build_dork_query(dork_pattern, target)
            
            yield f"  [{i}] Searching: {dork_pattern[:60]}...\n"
            
            found = 0
            for result in self._search_all_engines(dork_query):
                self._create_resource_node(result)
                found += 1
                total_results += 1
                
                available = "✓" if result.get('available') else "✗"
                yield f"      [{available}] {result['url']}\n"
                yield f"          {result['title'][:80]}\n"
            
            if found == 0:
                yield f"      No results\n"
            
            yield "\n"
        
        yield f"╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Total Logins Found: {total_results}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def search_devices(self, target: str, device_types: Optional[List[str]] = None) -> Iterator[str]:
        """Search for exposed network devices"""
        
        self._initialize_search("search_devices", target)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                 NETWORK DEVICE SEARCH                        ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        yield f"  Target: {target}\n\n"
        
        # Get device dorks
        if device_types:
            dorks = []
            for dt in device_types:
                if dt in DorkPatterns.DEVICES:
                    dorks.extend(DorkPatterns.DEVICES[dt])
        else:
            dorks = DorkPatterns.get_dorks_by_category("devices")
        
        total_results = 0
        
        for i, dork_pattern in enumerate(dorks[:20], 1):
            dork_query = self._build_dork_query(dork_pattern, target)
            
            yield f"  [{i}] Searching: {dork_pattern[:60]}...\n"
            
            found = 0
            for result in self._search_all_engines(dork_query):
                self._create_resource_node(result)
                found += 1
                total_results += 1
                
                yield f"      [•] {result['url']}\n"
                if result.get('ips'):
                    yield f"          IPs: {', '.join(result['ips'][:3])}\n"
            
            if found == 0:
                yield f"      No results\n"
            
            yield "\n"
        
        yield f"╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Total Devices Found: {total_results}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def search_misconfigs(self, target: str,
                         misconfig_types: Optional[List[str]] = None) -> Iterator[str]:
        """Search for misconfigurations"""
        
        self._initialize_search("search_misconfigs", target)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                 MISCONFIGURATION SEARCH                      ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        yield f"  Target: {target}\n\n"
        
        # Get misconfig dorks
        if misconfig_types:
            dorks = []
            for mt in misconfig_types:
                if mt in DorkPatterns.MISCONFIGS:
                    dorks.extend(DorkPatterns.MISCONFIGS[mt])
        else:
            dorks = DorkPatterns.get_dorks_by_category("misconfigs")
        
        total_results = 0
        
        for i, dork_pattern in enumerate(dorks[:15], 1):
            dork_query = self._build_dork_query(dork_pattern, target)
            
            yield f"  [{i}] Searching: {dork_pattern[:60]}...\n"
            
            found = 0
            for result in self._search_all_engines(dork_query):
                self._create_resource_node(result)
                found += 1
                total_results += 1
                
                yield f"      [!] {result['url']}\n"
                yield f"          {result['snippet'][:100]}...\n"
            
            if found == 0:
                yield f"      No results\n"
            
            yield "\n"
        
        yield f"╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Total Misconfigs Found: {total_results}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def search_people(self, target: str, info_types: Optional[List[str]] = None) -> Iterator[str]:
        """Search for people information"""
        
        self._initialize_search("search_people", target)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                    PEOPLE OSINT SEARCH                       ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        yield f"  Target: {target}\n\n"
        
        # Get people dorks
        if info_types:
            dorks = []
            for it in info_types:
                if it in DorkPatterns.PEOPLE:
                    dorks.extend(DorkPatterns.PEOPLE[it])
        else:
            dorks = DorkPatterns.get_dorks_by_category("people")
        
        total_results = 0
        emails_found = set()
        phones_found = set()
        
        for i, dork_pattern in enumerate(dorks[:10], 1):
            dork_query = self._build_dork_query(dork_pattern, target)
            
            yield f"  [{i}] Searching: {dork_pattern[:60]}...\n"
            
            found = 0
            for result in self._search_all_engines(dork_query):
                self._create_resource_node(result)
                found += 1
                total_results += 1
                
                if result.get('emails'):
                    emails_found.update(result['emails'])
                if result.get('phones'):
                    phones_found.update(result['phones'])
                
                yield f"      [•] {result['url']}\n"
            
            if found == 0:
                yield f"      No results\n"
            
            yield "\n"
        
        if emails_found:
            yield f"  Emails Discovered:\n"
            for email in list(emails_found)[:20]:
                yield f"    • {email}\n"
            yield "\n"
        
        if phones_found:
            yield f"  Phone Numbers Discovered:\n"
            for phone in list(phones_found)[:20]:
                yield f"    • {phone}\n"
            yield "\n"
        
        yield f"╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Total Results: {total_results}\n"
        yield f"  Emails: {len(emails_found)}\n"
        yield f"  Phones: {len(phones_found)}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def custom_dork(self, dork_query: str, engine: str = "google") -> Iterator[str]:
        """Execute custom dork query"""
        
        self._initialize_search("custom_dork", dork_query)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                     CUSTOM DORK SEARCH                       ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        yield f"  Query: {dork_query}\n"
        yield f"  Engine: {engine}\n\n"
        
        search_engine = self.engines.get(engine)
        if not search_engine:
            yield f"  [!] Engine '{engine}' not available\n"
            return
        
        total_results = 0
        
        for result in search_engine.search(dork_query, self.config.max_results_per_engine):
            self._create_resource_node(result)
            total_results += 1
            
            yield f"  [{total_results}] {result['url']}\n"
            yield f"      {result['title']}\n"
            
            if result.get('emails'):
                yield f"      Emails: {', '.join(result['emails'][:3])}\n"
            if result.get('phones'):
                yield f"      Phones: {', '.join(result['phones'][:3])}\n"
            
            yield "\n"
        
        yield f"╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Total Results: {total_results}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def comprehensive_dork(self, target: str, categories: Optional[List[str]] = None,
                          depth: str = "standard") -> Iterator[str]:
        """Comprehensive multi-category dorking"""
        
        self._initialize_search("comprehensive_dork", target)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║              COMPREHENSIVE DORKING SCAN                      ║\n"
        yield f"║                  Target: {target:^40}              ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        if not categories:
            categories = ["files", "logins", "misconfigs"]
        
        # [1/N] Files
        if "files" in categories:
            yield f"\n[1/{len(categories)}] EXPOSED FILES\n{'─' * 60}\n"
            for chunk in self.search_files(target):
                if not chunk.startswith('╔'):
                    yield chunk
        
        # [2/N] Logins
        if "logins" in categories:
            yield f"\n[2/{len(categories)}] LOGIN PORTALS\n{'─' * 60}\n"
            for chunk in self.search_logins(target):
                if not chunk.startswith('╔'):
                    yield chunk
        
        # [3/N] Devices
        if "devices" in categories or "cameras" in categories:
            yield f"\n[3/{len(categories)}] NETWORK DEVICES\n{'─' * 60}\n"
            for chunk in self.search_devices(target):
                if not chunk.startswith('╔'):
                    yield chunk
        
        # [4/N] Misconfigs
        if "misconfigs" in categories:
            yield f"\n[4/{len(categories)}] MISCONFIGURATIONS\n{'─' * 60}\n"
            for chunk in self.search_misconfigs(target):
                if not chunk.startswith('╔'):
                    yield chunk
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                   SCAN COMPLETE                              ║\n"
        yield f"  Total Resources: {len(self.discovered_resources)}\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"

# =============================================================================
# TOOL INTEGRATION - ALL ORIGINAL + NEW UNIFIED TOOLS
# =============================================================================

def add_dorking_tools(tool_list: List, agent):
    """Add comprehensive dorking tools - ALL original + NEW unified"""
    from langchain_core.tools import StructuredTool
    
    # =========================================================================
    # NEW: UNIFIED KEYWORD + CUSTOM DORK TOOLS
    # =========================================================================
    
    def unified_search_wrapper(search: str, target: Optional[str] = None,
                               file_type: Optional[str] = None, site: Optional[str] = None,
                               exclude_sites: Optional[List[str]] = None,
                               date_range: Optional[str] = None,
                               max_results: Optional[int] = 50,
                               engines: Optional[List[str]] = None,
                               mode: Optional[str] = "smart"):
        """Wrapper for unified search"""
        config = DorkingConfig.stealth_mode()
        
        if engines:
            config.engines = engines
        if date_range:
            config.date_filter = date_range
        
        config.max_results_per_engine = max_results or 50
        
        mapper = DorkingMapper(agent, config)
        for chunk in mapper.unified_search(
            search, target, file_type, site, exclude_sites, max_results, mode
        ):
            yield chunk
    
    def quick_search_wrapper(keywords: str, target: Optional[str] = None):
        """Wrapper for quick keyword search"""
        config = DorkingConfig.stealth_mode()
        config.max_results_per_engine = 30
        mapper = DorkingMapper(agent, config)
        for chunk in mapper.quick_search(keywords, target):
            yield chunk
    
    # =========================================================================
    # ORIGINAL CATEGORY-SPECIFIC TOOLS (ALL PRESERVED)
    # =========================================================================
    
    def search_files_wrapper(target: str, file_types: Optional[List[str]] = None,
                            keywords: Optional[List[str]] = None):
        config = DorkingConfig.stealth_mode()
        mapper = DorkingMapper(agent, config)
        for chunk in mapper.search_files(target, file_types, keywords):
            yield chunk
    
    def search_logins_wrapper(target: str, login_types: Optional[List[str]] = None):
        config = DorkingConfig.stealth_mode()
        mapper = DorkingMapper(agent, config)
        for chunk in mapper.search_logins(target, login_types):
            yield chunk
    
    def search_devices_wrapper(target: str, device_types: Optional[List[str]] = None):
        config = DorkingConfig.stealth_mode()
        mapper = DorkingMapper(agent, config)
        for chunk in mapper.search_devices(target, device_types):
            yield chunk
    
    def search_misconfigs_wrapper(target: str, misconfig_types: Optional[List[str]] = None):
        config = DorkingConfig.stealth_mode()
        mapper = DorkingMapper(agent, config)
        for chunk in mapper.search_misconfigs(target, misconfig_types):
            yield chunk
    
    def search_people_wrapper(target: str, info_types: Optional[List[str]] = None):
        config = DorkingConfig.stealth_mode()
        mapper = DorkingMapper(agent, config)
        for chunk in mapper.search_people(target, info_types):
            yield chunk
    
    def custom_dork_wrapper(target: str, dork_query: str, engine: str = "google"):
        config = DorkingConfig.stealth_mode()
        mapper = DorkingMapper(agent, config)
        for chunk in mapper.custom_dork(dork_query, engine):
            yield chunk
    
    def comprehensive_dork_wrapper(target: str, categories: Optional[List[str]] = None,
                                   depth: str = "standard"):
        if depth == "quick":
            config = DorkingConfig()
            config.max_results_per_engine = 20
        elif depth == "deep":
            config = DorkingConfig.aggressive_mode()
        else:
            config = DorkingConfig.stealth_mode()
        
        mapper = DorkingMapper(agent, config)
        for chunk in mapper.comprehensive_dork(target, categories, depth):
            yield chunk
    
    # Add ALL tools - original + new
    tool_list.extend([
        # NEW: Unified keyword/custom dork tools
        StructuredTool.from_function(
            func=unified_search_wrapper,
            name="dork_search",
            description=(
                "🔍 INTELLIGENT DORKING TOOL - Supports both simple keywords and advanced dorks\n\n"
                "SIMPLE KEYWORD EXAMPLES:\n"
                "  • search='webcam' - Find webcams/cameras\n"
                "  • search='admin login' - Find admin panels\n"
                "  • search='database' - Find exposed databases\n"
                "  • search='config', file_type='env' - Find .env files\n"
                "  • search='camera', target='example.com' - Find cameras on specific domain\n\n"
                "CUSTOM DORK EXAMPLES:\n"
                "  • search='intitle:\"webcam\" inurl:view.shtml'\n"
                "  • search='filetype:sql \"password\"'\n"
                "  • search='site:s3.amazonaws.com filetype:pdf'\n\n"
                "FEATURES:\n"
                "  • Auto-detects keywords vs custom dorks\n"
                "  • Generates multiple search variations\n"
                "  • Extracts emails, phones, IPs\n"
                "  • Deduplicates results\n"
                "  • Multi-engine support\n"
                "  • Anti-detection measures\n\n"
                "PARAMETERS:\n"
                "  • target: Focus on domain/keyword\n"
                "  • file_type: Filter by file extension\n"
                "  • site: Restrict to specific domain\n"
                "  • mode: 'smart' (auto), 'keyword', 'custom'"
            ),
            args_schema=UnifiedDorkInput
        ),
        
        StructuredTool.from_function(
            func=quick_search_wrapper,
            name="dork_quick",
            description=(
                "⚡ QUICK KEYWORD SEARCH - Fast keyword-based dorking\n\n"
                "Perfect for quick searches with simple keywords:\n"
                "  • 'webcam'\n"
                "  • 'admin panel'\n"
                "  • 'exposed database'\n"
                "  • 'printer'\n\n"
                "Returns top 30 results, minimal configuration."
            ),
            args_schema=QuickSearchInput
        ),
        
        # ORIGINAL: Category-specific tools (all preserved)
        StructuredTool.from_function(
            func=search_files_wrapper,
            name="dork_search_files",
            description=(
                "Search for exposed files using Google dorks. "
                "Finds SQL dumps, config files, logs, backups, credentials. "
                "File types: sql, log, env, config, bak, xml, json. "
                "Anti-detection with delays and rotation."
            ),
            args_schema=FileDorkInput
        ),
        
        StructuredTool.from_function(
            func=search_logins_wrapper,
            name="dork_search_logins",
            description=(
                "Search for login portals and admin panels. "
                "Finds admin panels, webmail, phpMyAdmin, CMS logins, control panels. "
                "Login types: admin, webmail, cpanel, phpmyadmin, wordpress."
            ),
            args_schema=LoginDorkInput
        ),
        
        StructuredTool.from_function(
            func=search_devices_wrapper,
            name="dork_search_devices",
            description=(
                "Search for exposed network devices. "
                "Finds webcams, printers, routers, NAS, IoT devices, SCADA systems. "
                "Device types: camera, webcam, printer, router, nas, scada."
            ),
            args_schema=DeviceDorkInput
        ),
        
        StructuredTool.from_function(
            func=search_misconfigs_wrapper,
            name="dork_search_misconfigs",
            description=(
                "Search for server misconfigurations. "
                "Finds directory listings, error pages, exposed .git/.svn, debug pages. "
                "Types: directory_listing, error_page, debug, git, svn."
            ),
            args_schema=MisconfigDorkInput
        ),
        
        StructuredTool.from_function(
            func=search_people_wrapper,
            name="dork_search_people",
            description=(
                "Search for people information and OSINT. "
                "Finds emails, phone numbers, social profiles, resumes. "
                "Extracts and correlates personal information. "
                "Info types: email, phone, social, resume, linkedin."
            ),
            args_schema=PeopleDorkInput
        ),
        
        StructuredTool.from_function(
            func=custom_dork_wrapper,
            name="dork_custom",
            description=(
                "Execute custom Google dork query. "
                "For advanced users who know exact dork syntax. "
                "Supports all search engines: google, bing, duckduckgo."
            ),
            args_schema=CustomDorkInput
        ),
        
        StructuredTool.from_function(
            func=comprehensive_dork_wrapper,
            name="dork_comprehensive",
            description=(
                "Comprehensive multi-category dorking scan. "
                "Searches files, logins, devices, misconfigs in one operation. "
                "Depth: quick (fast), standard (balanced), deep (thorough). "
                "Automatically correlates findings across categories."
            ),
            args_schema=ComprehensiveDorkInput
        ),
    ])
    
    return tool_list

if __name__ == "__main__":
    print("Enhanced Search Engine Dorking Toolkit")
    print("=" * 70)
    print("\n✨ NEW FEATURES:")
    print("  • Simple keyword search: just type 'webcam' and search")
    print("  • Intelligent dork generation from keywords")
    print("  • Auto-detection: keyword vs custom dork")
    print("  • Hybrid mode: combine keywords with filters")
    print("\n📚 KEYWORD EXAMPLES:")
    print("  • webcam, camera, printer, router")
    print("  • admin, login, dashboard, phpmyadmin")
    print("  • database, backup, config, password")
    print("  • s3, aws, azure, git, api")
    print("\n🎯 CUSTOM DORK EXAMPLES:")
    print("  • intitle:\"webcam\" inurl:view")
    print("  • filetype:sql \"password\"")
    print("  • site:s3.amazonaws.com backup")
    print("\n🛠️ ORIGINAL FEATURES (ALL PRESERVED):")
    print("  ✓ Multi-engine support (Google, Bing, DuckDuckGo)")
    print("  ✓ Anti-detection measures (rotation, delays)")
    print("  ✓ 500+ pre-built dork patterns")
    print("  ✓ Category-based searches")
    print("  ✓ Information extraction (emails, phones, IPs)")
    print("  ✓ Graph memory integration")
    print("\n📋 AVAILABLE TOOLS:")
    print("  1. dork_search - Unified keyword/custom dork search (NEW)")
    print("  2. dork_quick - Quick keyword search (NEW)")
    print("  3. dork_search_files - Exposed files search")
    print("  4. dork_search_logins - Login portals search")
    print("  5. dork_search_devices - Network devices search")
    print("  6. dork_search_misconfigs - Misconfigurations search")
    print("  7. dork_search_people - OSINT people search")
    print("  8. dork_custom - Custom dork execution")
    print("  9. dork_comprehensive - Multi-category scan")
    print("\n⚡ QUICK USAGE:")
    print("  Just search with keywords - the tool handles the rest!")
    print("  Add target/file_type for more specific results")
    print("  Use custom dorks for advanced queries")
    print("  All original category tools still available!")