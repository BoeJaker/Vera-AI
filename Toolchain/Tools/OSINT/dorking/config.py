#!/usr/bin/env python3
"""
Configuration classes and enums for the dorking toolkit.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional


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
    
    @classmethod
    def balanced_mode(cls) -> 'DorkingConfig':
        """Balanced speed and stealth"""
        return cls(
            engines=["google", "bing", "duckduckgo"],
            min_delay=3.0,
            max_delay=8.0,
            rotate_sessions=True,
            session_rotation_interval=10,
            use_random_user_agents=True,
            max_threads=3
        )