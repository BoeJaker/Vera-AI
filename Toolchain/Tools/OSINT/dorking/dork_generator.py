#!/usr/bin/env python3
"""
Intelligent dork query generator from keywords.

Maps common keywords to effective dork patterns and provides
smart query enhancement with filters.
"""

from typing import List, Optional


class DorkGenerator:
    """
    Intelligent dork query generator from keywords.
    Maps common keywords to effective dork patterns.
    """
    
    # =========================================================================
    # KEYWORD PATTERNS - Maps keywords to dork templates
    # =========================================================================
    
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
    
    # =========================================================================
    # CORE METHODS
    # =========================================================================
    
    @classmethod
    def is_custom_dork(cls, query: str) -> bool:
        """
        Detect if query contains dork operators.
        
        Args:
            query: Search query to check
        
        Returns:
            True if query contains dork operators
        """
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
        """
        Generate generic dork patterns from arbitrary keywords.
        
        Args:
            keywords: Keywords to convert
            max_dorks: Maximum dorks to generate
        
        Returns:
            List of generic dork patterns
        """
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
        
        Args:
            query: Base query (keyword or dork)
            target: Optional target term
            file_type: Optional file type filter
            site: Optional site restriction
            exclude_sites: Optional sites to exclude
        
        Returns:
            Enhanced query string
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
    
    @classmethod
    def get_keyword_suggestions(cls, partial: str) -> List[str]:
        """
        Get keyword suggestions based on partial input.
        
        Args:
            partial: Partial keyword
        
        Returns:
            List of matching keywords
        """
        partial_lower = partial.lower()
        return [
            keyword for keyword in cls.KEYWORD_PATTERNS.keys()
            if partial_lower in keyword
        ]
    
    @classmethod
    def get_all_keywords(cls) -> List[str]:
        """Get list of all recognized keywords"""
        return list(cls.KEYWORD_PATTERNS.keys())