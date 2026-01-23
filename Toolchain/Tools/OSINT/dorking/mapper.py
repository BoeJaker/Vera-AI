#!/usr/bin/env python3
"""
DorkingMapper - Main orchestrator for dorking operations.

Coordinates search engines, memory integration, and result processing.
"""

import re
import hashlib
from typing import Iterator, Dict, Any, Optional, List, Set
from datetime import datetime
import logging

import requests

from .config import DorkingConfig
from .dork_patterns import DorkPatterns
from .dork_generator import DorkGenerator
from .search_engines import GoogleSearchEngine, BingSearchEngine, DuckDuckGoSearchEngine

logger = logging.getLogger(__name__)


class DorkingMapper:
    """
    Dorking mapper with multi-engine support and memory integration.
    Supports both intelligent keyword search and custom dork queries.
    """
    
    def __init__(self, agent, config: DorkingConfig):
        """
        Initialize DorkingMapper.
        
        Args:
            agent: Agent instance with memory system
            config: DorkingConfig instance
        """
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
    
    # =========================================================================
    # MEMORY INTEGRATION
    # =========================================================================
    
    def _initialize_search(self, tool_name: str, query: str):
        """Initialize search context in memory"""
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
        except Exception as e:
            logger.warning(f"Failed to create search memory: {e}")
    
    def _create_resource_node(self, resource_data: Dict[str, Any]) -> str:
        """Create discovered resource node in memory"""
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
    
    # =========================================================================
    # RESULT PROCESSING
    # =========================================================================
    
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
        """Build complete dork query with filters"""
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
    # UNIFIED KEYWORD + CUSTOM DORK SEARCH
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
        
        Yields:
            Formatted result strings
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
    # CATEGORY-SPECIFIC DORKING OPERATIONS
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