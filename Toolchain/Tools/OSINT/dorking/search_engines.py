#!/usr/bin/env python3
"""
Search engine implementations with anti-detection measures.

Supports:
- Google Search
- Bing Search
- DuckDuckGo Search
- Yahoo Search (future)
- Yandex Search (future)

Features:
- User agent rotation
- Session management
- Random delays
- Referrer headers
- Captcha detection
"""

import time
import random
import urllib.parse
from typing import List, Dict, Any
import logging

import requests
from bs4 import BeautifulSoup

# Optional fake user agent
try:
    from fake_useragent import UserAgent
    FAKE_UA_AVAILABLE = True
except ImportError:
    FAKE_UA_AVAILABLE = False

logger = logging.getLogger(__name__)


class BaseSearchEngine:
    """Base class for search engines with anti-detection"""
    
    def __init__(self, config):
        """
        Initialize search engine.
        
        Args:
            config: DorkingConfig instance
        """
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
    
    def __init__(self, config):
        super().__init__(config)
        self.base_url = "https://www.google.com/search"
    
    def search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """
        Search Google.
        
        Args:
            query: Search query
            max_results: Maximum results to return
        
        Returns:
            List of search result dictionaries
        """
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
    
    def __init__(self, config):
        super().__init__(config)
        self.base_url = "https://www.bing.com/search"
    
    def search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """
        Search Bing.
        
        Args:
            query: Search query
            max_results: Maximum results to return
        
        Returns:
            List of search result dictionaries
        """
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
    
    def __init__(self, config):
        super().__init__(config)
        self.base_url = "https://html.duckduckgo.com/html/"
    
    def search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """
        Search DuckDuckGo.
        
        Args:
            query: Search query
            max_results: Maximum results to return
        
        Returns:
            List of search result dictionaries
        """
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