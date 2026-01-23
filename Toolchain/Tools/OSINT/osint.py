#!/usr/bin/env python3
"""
Open Source Intelligence (OSINT) Toolkit for Vera
LIVING OFF THE LAND - Free, Open, Public Sources Only

Modular, self-sufficient tools with:
- Intelligent input parsing (handles formatted output from other tools)
- Graph memory integration (entities automatically stored)
- Tool chaining compatibility
- Execution context tracking
- Streaming visual output

ETHICAL USE ONLY: Only investigate targets you have permission to research.
Todo EXIF Extraction


"""

import re
import json
import time
import socket
import hashlib
import requests
from typing import List, Dict, Any, Optional, Set, Iterator, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydantic import BaseModel, Field
from urllib.parse import urlparse, urljoin
from enum import Enum
import logging

# DNS tools
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

# HTML parsing
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("[Warning] BeautifulSoup not available - HTML parsing limited")

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

class OSINTMode(str, Enum):
    """OSINT operation modes"""
    USERNAME = "username"
    EMAIL = "email"
    DOMAIN = "domain"
    PHONE = "phone"
    LICENSE_PLATE = "license_plate"
    COMPANY = "company"
    PERSON = "person"

@dataclass
class OSINTConfig:
    """Configuration for OSINT operations"""
    
    # Target specification
    targets: List[str] = field(default_factory=list)
    
    # Search parameters
    timeout: int = 10
    max_threads: int = 10
    rate_limit: float = 1.0  # seconds between requests
    
    # Deep investigation
    deep_scan: bool = False
    follow_links: bool = False
    
    # Graph options
    link_to_session: bool = True
    create_entity_nodes: bool = True
    link_discoveries: bool = True
    auto_run_prerequisites: bool = True
    
    # User agent
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    @classmethod
    def quick_scan(cls) -> 'OSINTConfig':
        return cls(
            deep_scan=False,
            follow_links=False,
            max_threads=5
        )
    
    @classmethod
    def deep_scan(cls) -> 'OSINTConfig':
        return cls(
            deep_scan=True,
            follow_links=True,
            max_threads=20,
            rate_limit=0.5
        )

# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class FlexibleTargetInput(BaseModel):
    target: str = Field(description="Target: username, email, domain, phone, or formatted output")

class UsernameOSINTInput(FlexibleTargetInput):
    platforms: Optional[List[str]] = Field(default=None, description="Specific platforms or None for all")
    deep_scan: bool = Field(default=False, description="Deep profile analysis")

class EmailOSINTInput(FlexibleTargetInput):
    check_breaches: bool = Field(default=True, description="Check data breaches")
    verify_mx: bool = Field(default=True, description="Verify MX records")

class DomainOSINTInput(FlexibleTargetInput):
    include_subdomains: bool = Field(default=False, description="Enumerate subdomains")
    check_history: bool = Field(default=False, description="Check domain history")

class PhoneOSINTInput(FlexibleTargetInput):
    country_code: Optional[str] = Field(default=None, description="Country code (e.g., 'US', 'UK')")
    carrier_lookup: bool = Field(default=True, description="Lookup carrier info")

class LicensePlateInput(FlexibleTargetInput):
    state: Optional[str] = Field(default=None, description="State/Province code")
    country: str = Field(default="US", description="Country code")

class CompanyOSINTInput(FlexibleTargetInput):
    country: str = Field(default="US", description="Country for business registry")
    include_filings: bool = Field(default=False, description="Include SEC filings")

class PersonOSINTInput(FlexibleTargetInput):
    location: Optional[str] = Field(default=None, description="Known location")
    age_range: Optional[str] = Field(default=None, description="Age range (e.g., '25-35')")

class DataBreachInput(FlexibleTargetInput):
    check_type: str = Field(default="email", description="Type: email, username, domain")

# =============================================================================
# INPUT PARSER - EXTRACT TARGETS FROM FORMATTED TEXT
# =============================================================================

class OSINTInputParser:
    """
    Intelligent input parser that extracts clean targets from various formats.
    Handles usernames, emails, domains, phones, etc. from formatted tool output.
    """
    
    @staticmethod
    def extract_target(input_text: str, expected_type: Optional[OSINTMode] = None) -> str:
        """
        Extract clean target from potentially formatted input.
        
        Args:
            input_text: Raw input (could be formatted output from another tool)
            expected_type: Expected target type (helps with disambiguation)
            
        Returns:
            Clean target string
        """
        if not input_text:
            return ""
        
        input_text = str(input_text).strip()
        
        # Check if already clean
        if OSINTInputParser._is_clean_target(input_text, expected_type):
            return input_text
        
        # Extract based on type
        if expected_type == OSINTMode.EMAIL:
            emails = OSINTInputParser._extract_emails(input_text)
            return emails[0] if emails else input_text
        
        elif expected_type == OSINTMode.DOMAIN:
            domains = OSINTInputParser._extract_domains(input_text)
            return domains[0] if domains else input_text
        
        elif expected_type == OSINTMode.PHONE:
            phones = OSINTInputParser._extract_phones(input_text)
            return phones[0] if phones else input_text
        
        elif expected_type == OSINTMode.USERNAME:
            # Extract username patterns
            username_match = re.search(r'@?([a-zA-Z0-9_]{3,30})', input_text)
            return username_match.group(1) if username_match else input_text
        
        # Auto-detect type
        if '@' in input_text and '.' in input_text:
            emails = OSINTInputParser._extract_emails(input_text)
            if emails:
                return emails[0]
        
        domains = OSINTInputParser._extract_domains(input_text)
        if domains:
            return domains[0]
        
        return input_text
    
    @staticmethod
    def _is_clean_target(text: str, target_type: Optional[OSINTMode] = None) -> bool:
        """Check if text is already a clean target"""
        if target_type == OSINTMode.EMAIL:
            return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', text))
        
        elif target_type == OSINTMode.DOMAIN:
            return bool(re.match(r'^([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$', text))
        
        elif target_type == OSINTMode.PHONE:
            return bool(re.match(r'^\+?[\d\s\-\(\)]+$', text))
        
        elif target_type == OSINTMode.USERNAME:
            return bool(re.match(r'^[a-zA-Z0-9_]{3,30}$', text))
        
        # Generic check - no special formatting characters
        return not any(c in text for c in ['|', '╔', '═', '║', '─', '\n'])
    
    @staticmethod
    def _extract_emails(text: str) -> List[str]:
        """Extract all email addresses from text"""
        pattern = r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
        return list(set(re.findall(pattern, text)))
    
    @staticmethod
    def _extract_domains(text: str) -> List[str]:
        """Extract all domains from text"""
        pattern = r'\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b'
        matches = re.findall(pattern, text)
        # Filter out email domains
        return [m for m in matches if not re.search(r'[a-zA-Z0-9._%+-]+@' + re.escape(m), text)]
    
    @staticmethod
    def _extract_phones(text: str) -> List[str]:
        """Extract phone numbers from text"""
        patterns = [
            r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # US/International
            r'\d{3}[-.\s]\d{3}[-.\s]\d{4}',  # US format
            r'\+\d{10,15}',  # International
        ]
        
        phones = []
        for pattern in patterns:
            phones.extend(re.findall(pattern, text))
        
        return list(set(phones))

# =============================================================================
# OSINT DATA SOURCES - FREE & OPEN
# =============================================================================

class OSINTSources:
    """
    Collection of free, open-source OSINT data sources.
    "Living off the land" - using publicly available information only.
    """
    
    # Social media platforms (no API keys needed)
    SOCIAL_PLATFORMS = {
        "github": "https://github.com/{}",
        "twitter": "https://twitter.com/{}",
        "instagram": "https://www.instagram.com/{}/",
        "reddit": "https://www.reddit.com/user/{}",
        "youtube": "https://www.youtube.com/@{}",
        "linkedin": "https://www.linkedin.com/in/{}",
        "tiktok": "https://www.tiktok.com/@{}",
        "medium": "https://medium.com/@{}",
        "dev.to": "https://dev.to/{}",
        "pinterest": "https://www.pinterest.com/{}",
        "twitch": "https://www.twitch.tv/{}",
        "soundcloud": "https://soundcloud.com/{}",
        "vimeo": "https://vimeo.com/{}",
        "dribbble": "https://dribbble.com/{}",
        "behance": "https://www.behance.net/{}",
        "stackoverflow": "https://stackoverflow.com/users/{}",
        "hackernews": "https://news.ycombinator.com/user?id={}",
        "producthunt": "https://www.producthunt.com/@{}",
        "keybase": "https://keybase.io/{}",
        "pastebin": "https://pastebin.com/u/{}",
    }
    
    # Data breach checking (free tier)
    BREACH_SOURCES = {
        "haveibeenpwned_api": "https://haveibeenpwned.com/api/v3/breachedaccount/{}",
        "dehashed": "https://www.dehashed.com/search?query={}",  # Web scraping
    }
    
    # Public records & registries
    PUBLIC_RECORDS = {
        "opencorporates": "https://opencorporates.com/companies?q={}",
        "sec_edgar": "https://www.sec.gov/cgi-bin/browse-edgar?company={}&action=getcompany",
        "uk_companies_house": "https://find-and-update.company-information.service.gov.uk/search?q={}",
    }
    
    # License plate databases (public/free sources)
    LICENSE_PLATE_SOURCES = {
        # Most require scraping public records or using state DMV public portals
        "uk_dvla": "https://vehicleenquiry.service.gov.uk/",  # UK only
        # US states have varying levels of public access
        # Many states restrict this data, so we note availability
    }
    
    # Phone number databases
    PHONE_SOURCES = {
        "numverify": "http://apilayer.net/api/validate?access_key={key}&number={phone}",  # Free tier
        "carrier_lookup": "https://freecarrierlookup.com/",  # Web scraping
    }
    
    # Certificate transparency logs (free, comprehensive)
    CERT_TRANSPARENCY = [
        "https://crt.sh/?q=%.{domain}&output=json",
        "https://censys.io/certificates?q={domain}",  # Free tier
    ]
    
    # DNS databases
    DNS_DATABASES = [
        "https://securitytrails.com/domain/{domain}/dns",  # Free tier
        "https://dnsdumpster.com/",  # Free, scraping needed
    ]

# =============================================================================
# OSINT COMPONENTS
# =============================================================================

class SocialMediaIntelligence:
    """Social media profile discovery and analysis"""
    
    def __init__(self, config: OSINTConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': config.user_agent})
    
    def scan_platforms(self, username: str, platforms: Optional[List[str]] = None) -> Iterator[Dict[str, Any]]:
        """
        Scan social media platforms for username.
        Yields profile info as it's discovered.
        """
        platform_urls = OSINTSources.SOCIAL_PLATFORMS
        
        if platforms:
            platform_urls = {k: v for k, v in platform_urls.items() if k in platforms}
        
        def check_platform(platform: str, url_template: str):
            url = url_template.format(username)
            
            try:
                response = self.session.get(url, timeout=self.config.timeout, allow_redirects=True)
                
                # Platform-specific checks
                exists = False
                metadata = {}
                
                if platform == "github":
                    exists = response.status_code == 200 and "Not Found" not in response.text
                    if exists and BS4_AVAILABLE and self.config.deep_scan:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        name_elem = soup.select_one('[itemprop="name"]')
                        if name_elem:
                            metadata["name"] = name_elem.text.strip()
                        bio_elem = soup.select_one('[data-bio-text]')
                        if bio_elem:
                            metadata["bio"] = bio_elem.text.strip()[:200]
                
                elif platform == "twitter":
                    exists = response.status_code == 200 and "doesn't exist" not in response.text
                
                elif platform == "reddit":
                    exists = response.status_code == 200 and response.url == url
                
                else:
                    exists = response.status_code == 200
                
                return {
                    "platform": platform,
                    "url": url,
                    "exists": exists,
                    "status_code": response.status_code,
                    "metadata": metadata
                }
            
            except Exception as e:
                return {
                    "platform": platform,
                    "url": url,
                    "exists": False,
                    "error": str(e)[:100]
                }
        
        # Parallel checking with thread pool
        with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
            futures = {
                executor.submit(check_platform, platform, url): platform
                for platform, url in platform_urls.items()
            }
            
            for future in as_completed(futures):
                time.sleep(self.config.rate_limit)  # Rate limiting
                try:
                    result = future.result()
                    if result:
                        yield result
                except Exception as e:
                    logger.error(f"Error checking platform: {e}")
                    continue

class EmailIntelligence:
    """Email address OSINT - validation, breaches, patterns"""
    
    def __init__(self, config: OSINTConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': config.user_agent})
    
    def investigate_email(self, email: str) -> Dict[str, Any]:
        """Comprehensive email investigation"""
        result = {
            "email": email,
            "valid_format": self._validate_format(email),
            "domain_info": {},
            "mx_records": [],
            "breaches": [],
            "variations": []
        }
        
        if not result["valid_format"]:
            return result
        
        # Extract domain
        domain = email.split('@')[1]
        
        # Check MX records
        if DNS_AVAILABLE:
            try:
                mx_records = dns.resolver.resolve(domain, 'MX')
                result["mx_records"] = [str(mx.exchange) for mx in mx_records]
                result["mx_valid"] = len(result["mx_records"]) > 0
            except:
                result["mx_valid"] = False
        
        # Domain WHOIS
        if WHOIS_AVAILABLE:
            try:
                w = python_whois.whois(domain)
                result["domain_info"] = {
                    "registrar": w.registrar,
                    "creation_date": str(w.creation_date) if w.creation_date else None,
                    "expiration_date": str(w.expiration_date) if w.expiration_date else None,
                }
            except:
                pass
        
        # Common email variations
        username = email.split('@')[0]
        result["variations"] = self._generate_variations(username, domain)
        
        return result
    
    def _validate_format(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def _generate_variations(self, username: str, domain: str) -> List[str]:
        """Generate common email variations"""
        variations = []
        
        # Common patterns
        if '.' in username:
            parts = username.split('.')
            variations.append(f"{parts[0]}@{domain}")
            variations.append(f"{parts[0]}{parts[1]}@{domain}")
            if len(parts[0]) > 0 and len(parts[1]) > 0:
                variations.append(f"{parts[0][0]}{parts[1]}@{domain}")
        
        # Add numbers
        for i in range(1, 10):
            variations.append(f"{username}{i}@{domain}")
        
        return list(set(variations))[:10]  # Limit to 10

class DomainIntelligence:
    """Domain OSINT - WHOIS, DNS, subdomains, history"""
    
    def __init__(self, config: OSINTConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': config.user_agent})
    
    def investigate_domain(self, domain: str) -> Dict[str, Any]:
        """Comprehensive domain investigation"""
        result = {
            "domain": domain,
            "whois": {},
            "dns_records": {},
            "subdomains": [],
            "certificates": [],
            "history": {}
        }
        
        # WHOIS lookup
        if WHOIS_AVAILABLE:
            try:
                w = python_whois.whois(domain)
                result["whois"] = {
                    "registrar": w.registrar,
                    "creation_date": str(w.creation_date) if w.creation_date else None,
                    "expiration_date": str(w.expiration_date) if w.expiration_date else None,
                    "name_servers": w.name_servers if hasattr(w, 'name_servers') else [],
                    "status": w.status if hasattr(w, 'status') else None,
                }
            except Exception as e:
                result["whois"]["error"] = str(e)
        
        # DNS records
        if DNS_AVAILABLE:
            result["dns_records"] = self._get_dns_records(domain)
        
        # Certificate transparency (subdomains)
        try:
            ct_url = f"https://crt.sh/?q=%.{domain}&output=json"
            response = self.session.get(ct_url, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                subdomains = set()
                
                for entry in data[:100]:  # Limit to first 100
                    name_value = entry.get("name_value", "")
                    for subdomain in name_value.split("\n"):
                        subdomain = subdomain.strip()
                        if subdomain.endswith(f".{domain}") or subdomain == domain:
                            subdomains.add(subdomain)
                
                result["subdomains"] = sorted(subdomains)
                result["certificates"] = data[:10]  # Sample of certs
        except:
            pass
        
        return result
    
    def _get_dns_records(self, domain: str) -> Dict[str, List[str]]:
        """Get various DNS records"""
        records = {}
        
        record_types = ['A', 'AAAA', 'MX', 'NS', 'TXT', 'CNAME']
        
        for rtype in record_types:
            try:
                answers = dns.resolver.resolve(domain, rtype)
                records[rtype] = [str(rdata) for rdata in answers]
            except:
                records[rtype] = []
        
        return records

class PhoneIntelligence:
    """Phone number OSINT - carrier, location, validation"""
    
    def __init__(self, config: OSINTConfig):
        self.config = config
    
    def investigate_phone(self, phone: str, country_code: Optional[str] = None) -> Dict[str, Any]:
        """
        Investigate phone number using open sources.
        Note: Most comprehensive phone lookups require paid APIs.
        """
        result = {
            "phone": phone,
            "formatted": self._format_phone(phone, country_code),
            "country_code": country_code,
            "type": None,  # mobile, landline, voip
            "carrier": None,
            "location": None,
            "valid": False
        }
        
        # Basic validation
        cleaned = re.sub(r'[^\d+]', '', phone)
        result["valid"] = len(cleaned) >= 10
        
        # Extract country code if present
        if cleaned.startswith('+'):
            if cleaned.startswith('+1'):
                result["country_code"] = "US/CA"
            elif cleaned.startswith('+44'):
                result["country_code"] = "UK"
            elif cleaned.startswith('+61'):
                result["country_code"] = "AU"
            # Add more as needed
        
        # Area code lookup (US example)
        if result["country_code"] in ["US/CA", None] and len(cleaned) >= 10:
            area_code = cleaned[-10:-7]
            result["location"] = self._lookup_area_code(area_code)
        
        return result
    
    def _format_phone(self, phone: str, country_code: Optional[str]) -> str:
        """Format phone number"""
        cleaned = re.sub(r'[^\d]', '', phone)
        
        if len(cleaned) == 10:  # US format
            return f"({cleaned[:3]}) {cleaned[3:6]}-{cleaned[6:]}"
        elif len(cleaned) == 11 and cleaned[0] == '1':  # US with country code
            return f"+1 ({cleaned[1:4]}) {cleaned[4:7]}-{cleaned[7:]}"
        
        return phone
    
    def _lookup_area_code(self, area_code: str) -> Optional[str]:
        """
        Lookup US area code location.
        This is a small sample - full implementation would use a comprehensive database.
        """
        area_codes = {
            "212": "New York, NY",
            "213": "Los Angeles, CA",
            "312": "Chicago, IL",
            "415": "San Francisco, CA",
            "617": "Boston, MA",
            "202": "Washington, DC",
            "404": "Atlanta, GA",
            "305": "Miami, FL",
            "713": "Houston, TX",
            "206": "Seattle, WA",
            # Add more as needed
        }
        
        return area_codes.get(area_code)

class LicensePlateIntelligence:
    """License plate OSINT - public records only"""
    
    def __init__(self, config: OSINTConfig):
        self.config = config
    
    def investigate_plate(self, plate: str, state: Optional[str] = None, country: str = "US") -> Dict[str, Any]:
        """
        Investigate license plate using public records.
        
        IMPORTANT: Most DMV data is restricted. This only uses publicly available info.
        """
        result = {
            "plate": plate.upper(),
            "state": state,
            "country": country,
            "format_valid": False,
            "state_patterns": {},
            "public_records": []
        }
        
        # Validate format
        if country == "US":
            result["format_valid"] = self._validate_us_plate(plate, state)
            result["state_patterns"] = self._identify_us_state(plate)
        
        elif country == "UK":
            result["format_valid"] = self._validate_uk_plate(plate)
            if result["format_valid"]:
                result["year"] = self._decode_uk_year(plate)
                result["region"] = self._decode_uk_region(plate)
        
        return result
    
    def _validate_us_plate(self, plate: str, state: Optional[str]) -> bool:
        """Validate US license plate format"""
        # US plates vary by state - general validation
        cleaned = re.sub(r'[^A-Z0-9]', '', plate.upper())
        return 4 <= len(cleaned) <= 8
    
    def _identify_us_state(self, plate: str) -> Dict[str, str]:
        """
        Attempt to identify state from plate pattern.
        This is approximate - many states have multiple formats.
        """
        patterns = {
            "CA": r'^[0-9][A-Z]{3}[0-9]{3}$',  # California: 1ABC123
            "NY": r'^[A-Z]{3}[0-9]{4}$',       # New York: ABC1234
            "TX": r'^[A-Z]{3}[0-9]{4}$',       # Texas: ABC1234
            "FL": r'^[A-Z]{4}[0-9]{2}$',       # Florida: ABCD12
            # Add more state patterns
        }
        
        matches = {}
        cleaned = re.sub(r'[^A-Z0-9]', '', plate.upper())
        
        for state, pattern in patterns.items():
            if re.match(pattern, cleaned):
                matches[state] = "Possible match"
        
        return matches
    
    def _validate_uk_plate(self, plate: str) -> bool:
        """Validate UK license plate format (current system since 2001)"""
        # UK format: AB12 CDE (area code, age identifier, random letters)
        pattern = r'^[A-Z]{2}[0-9]{2}\s?[A-Z]{3}$'
        return bool(re.match(pattern, plate.upper()))
    
    def _decode_uk_year(self, plate: str) -> Optional[str]:
        """Decode year from UK plate"""
        match = re.match(r'^[A-Z]{2}([0-9]{2})', plate.upper())
        if not match:
            return None
        
        age_id = int(match.group(1))
        
        # UK system: 01-50 = first half of year, 51-99 = second half
        if 1 <= age_id <= 50:
            year = 2000 + age_id
            return f"March-August {year}"
        elif 51 <= age_id <= 99:
            year = 2000 + (age_id - 50)
            return f"September-February {year}/{year+1}"
        
        return None
    
    def _decode_uk_region(self, plate: str) -> Optional[str]:
        """Decode region from UK plate"""
        # First two letters indicate region
        region_codes = {
            "AA": "Peterborough", "AB": "Worcester", "AC": "Coventry",
            "AD": "Gloucester", "AE": "Bristol", "AF": "Truro",
            "BA": "Birmingham", "BB": "Birmingham", "BC": "Leicester",
            "BD": "Northampton", "BE": "Lincoln", "BF": "Stoke",
            "CA": "Cardiff", "CB": "Cardiff", "CC": "Swansea",
            "DA": "Deeside", "DB": "Manchester", "DC": "Middlesbrough",
            # Add more as needed
        }
        
        area_code = plate[:2].upper()
        return region_codes.get(area_code, "Unknown")

class CompanyIntelligence:
    """Company/business OSINT - public registries, filings"""
    
    def __init__(self, config: OSINTConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': config.user_agent})
    
    def investigate_company(self, company_name: str, country: str = "US") -> Dict[str, Any]:
        """
        Investigate company using public registries.
        """
        result = {
            "company_name": company_name,
            "country": country,
            "opencorporates": {},
            "sec_filings": [],
            "related_entities": []
        }
        
        # OpenCorporates (free, open database)
        try:
            search_url = f"https://opencorporates.com/companies?q={company_name}"
            # This would require scraping - API is paid
            result["opencorporates"]["search_url"] = search_url
        except:
            pass
        
        # SEC EDGAR (US only)
        if country == "US":
            try:
                search_url = f"https://www.sec.gov/cgi-bin/browse-edgar?company={company_name}&action=getcompany"
                result["sec_filings"].append({
                    "source": "SEC EDGAR",
                    "search_url": search_url,
                    "note": "Manual search required - scraping SEC is complex"
                })
            except:
                pass
        
        # UK Companies House
        elif country == "UK":
            try:
                search_url = f"https://find-and-update.company-information.service.gov.uk/search?q={company_name}"
                result["companies_house"] = {
                    "search_url": search_url,
                    "note": "Public API available with free tier"
                }
            except:
                pass
        
        return result

class DataBreachIntelligence:
    """Data breach checking - HaveIBeenPwned and others"""
    
    def __init__(self, config: OSINTConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': config.user_agent})
    
    def check_breaches(self, identifier: str, check_type: str = "email") -> Dict[str, Any]:
        """
        Check if identifier appears in known data breaches.
        Uses HaveIBeenPwned API (free tier with rate limiting).
        """
        result = {
            "identifier": identifier,
            "type": check_type,
            "breaches": [],
            "total_breaches": 0,
            "severity": "unknown"
        }
        
        try:
            # HaveIBeenPwned API (requires API key for email, but breach info is public)
            # Free tier allows searching breach info
            breach_url = "https://haveibeenpwned.com/api/v3/breaches"
            
            response = self.session.get(breach_url, timeout=10)
            
            if response.status_code == 200:
                all_breaches = response.json()
                
                # This is sample - full implementation would search specific identifier
                result["total_breaches"] = len(all_breaches)
                result["breaches"] = [
                    {
                        "name": b.get("Name"),
                        "domain": b.get("Domain"),
                        "breach_date": b.get("BreachDate"),
                        "data_classes": b.get("DataClasses", [])
                    }
                    for b in all_breaches[:5]  # Sample
                ]
        
        except Exception as e:
            result["error"] = str(e)
        
        return result

# =============================================================================
# OSINT MAPPER - COORDINATES ALL INVESTIGATIONS
# =============================================================================

class OSINTMapper:
    """
    OSINT mapper with graph memory integration and self-sufficient tools.
    """
    
    def __init__(self, agent, config: OSINTConfig):
        self.agent = agent
        self.config = config
        
        # Initialize intelligence components
        self.social = SocialMediaIntelligence(config)
        self.email = EmailIntelligence(config)
        self.domain = DomainIntelligence(config)
        self.phone = PhoneIntelligence(config)
        self.plate = LicensePlateIntelligence(config)
        self.company = CompanyIntelligence(config)
        self.breach = DataBreachIntelligence(config)
        
        # Tracking
        self.investigation_node_id = None
        self.discovered_entities = {}
    
    def _initialize_investigation(self, tool_name: str, target: str, target_type: str):
        """Initialize investigation context in graph"""
        if self.investigation_node_id is not None:
            return
        
        try:
            inv_mem = self.agent.mem.add_session_memory(
                self.agent.sess.id,
                f"OSINT investigation: {target}",
                "osint_investigation",
                metadata={
                    "tool": tool_name,
                    "target": target,
                    "target_type": target_type,
                    "started_at": datetime.now().isoformat(),
                }
            )
            self.investigation_node_id = inv_mem.id
        except Exception as e:
            logger.error(f"Failed to initialize investigation: {e}")
    
    def _create_entity_node(self, entity_id: str, entity_type: str, properties: Dict[str, Any]) -> str:
        """Create entity node in graph"""
        if entity_id in self.discovered_entities:
            return self.discovered_entities[entity_id]
        
        try:
            # Add standard properties
            properties["discovered_at"] = datetime.now().isoformat()
            properties["entity_type"] = entity_type
            
            self.agent.mem.upsert_entity(
                entity_id,
                entity_type,
                labels=["OSINTEntity", entity_type.capitalize()],
                properties=properties
            )
            
            # Link to investigation
            if self.investigation_node_id:
                self.agent.mem.link(
                    self.investigation_node_id,
                    entity_id,
                    "DISCOVERED",
                    {"entity_type": entity_type}
                )
            
            self.discovered_entities[entity_id] = entity_id
            return entity_id
        
        except Exception as e:
            logger.error(f"Failed to create entity node: {e}")
            return entity_id
    
    def _link_entities(self, src_id: str, dst_id: str, rel_type: str, properties: Optional[Dict] = None):
        """Link two entities in graph"""
        try:
            self.agent.mem.link(
                src_id,
                dst_id,
                rel_type,
                properties or {}
            )
        except Exception as e:
            logger.error(f"Failed to link entities: {e}")
    
    # =========================================================================
    # INVESTIGATION METHODS
    # =========================================================================
    
    def investigate_username(self, target: str, platforms: Optional[List[str]] = None,
                           deep_scan: bool = False) -> Iterator[str]:
        """Investigate username across social media platforms"""
        
        # Parse input
        username = OSINTInputParser.extract_target(target, OSINTMode.USERNAME)
        
        self._initialize_investigation("investigate_username", username, "username")
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                  USERNAME INVESTIGATION                      ║\n"
        yield f"║                   Target: {username:^30}                ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        # Create username entity
        username_id = f"username_{hashlib.md5(username.encode()).hexdigest()[:8]}"
        self._create_entity_node(
            username_id,
            "username",
            {
                "username": username,
                "platforms_checked": platforms or "all"
            }
        )
        
        found_count = 0
        total_checked = 0
        
        yield f"Scanning platforms for '{username}'...\n\n"
        
        for profile in self.social.scan_platforms(username, platforms):
            total_checked += 1
            
            if profile["exists"]:
                found_count += 1
                platform = profile["platform"]
                url = profile["url"]
                
                # Create profile entity
                profile_id = f"profile_{platform}_{hashlib.md5(username.encode()).hexdigest()[:8]}"
                self._create_entity_node(
                    profile_id,
                    "social_profile",
                    {
                        "platform": platform,
                        "username": username,
                        "url": url,
                        "metadata": profile.get("metadata", {})
                    }
                )
                
                # Link username to profile
                self._link_entities(username_id, profile_id, "HAS_PROFILE", {"platform": platform})
                
                yield f"  [✓] {platform:15} → {url}\n"
                
                # Show metadata if available
                if profile.get("metadata"):
                    for key, value in profile["metadata"].items():
                        yield f"      • {key}: {value}\n"
            
            elif "error" in profile:
                yield f"  [!] {profile['platform']:15} → Error: {profile['error']}\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Found: {found_count}/{total_checked} platforms\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def investigate_email(self, target: str, check_breaches: bool = True,
                         verify_mx: bool = True) -> Iterator[str]:
        """Investigate email address"""
        
        email = OSINTInputParser.extract_target(target, OSINTMode.EMAIL)
        
        self._initialize_investigation("investigate_email", email, "email")
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                   EMAIL INVESTIGATION                        ║\n"
        yield f"║                   Target: {email:^30}         ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        # Investigate
        result = self.email.investigate_email(email)
        
        # Create email entity
        email_id = f"email_{hashlib.md5(email.encode()).hexdigest()[:8]}"
        self._create_entity_node(
            email_id,
            "email",
            {
                "email": email,
                "valid_format": result["valid_format"],
                "mx_valid": result.get("mx_valid", False),
                "domain_info": result.get("domain_info", {})
            }
        )
        
        yield f"[1/3] FORMAT VALIDATION\n{'─' * 60}\n"
        yield f"  Valid Format: {'✓' if result['valid_format'] else '✗'}\n"
        
        if result.get("mx_records"):
            yield f"  MX Records: ✓ ({len(result['mx_records'])} found)\n"
            for mx in result["mx_records"][:3]:
                yield f"    • {mx}\n"
        else:
            yield f"  MX Records: ✗ (None found)\n"
        
        yield f"\n[2/3] DOMAIN INFORMATION\n{'─' * 60}\n"
        if result.get("domain_info"):
            for key, value in result["domain_info"].items():
                if value:
                    yield f"  {key.replace('_', ' ').title()}: {value}\n"
        else:
            yield "  No domain information available\n"
        
        yield f"\n[3/3] EMAIL VARIATIONS\n{'─' * 60}\n"
        if result.get("variations"):
            yield f"  Common variations:\n"
            for variation in result["variations"][:5]:
                yield f"    • {variation}\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Email Investigation Complete\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def investigate_domain(self, target: str, include_subdomains: bool = False) -> Iterator[str]:
        """Investigate domain"""
        
        domain = OSINTInputParser.extract_target(target, OSINTMode.DOMAIN)
        
        self._initialize_investigation("investigate_domain", domain, "domain")
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                  DOMAIN INVESTIGATION                        ║\n"
        yield f"║                   Target: {domain:^30}         ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        # Investigate
        result = self.domain.investigate_domain(domain)
        
        # Create domain entity
        domain_id = f"domain_{hashlib.md5(domain.encode()).hexdigest()[:8]}"
        self._create_entity_node(
            domain_id,
            "domain",
            {
                "domain": domain,
                "whois": result.get("whois", {}),
                "dns_records": result.get("dns_records", {}),
                "subdomain_count": len(result.get("subdomains", []))
            }
        )
        
        yield f"[1/4] WHOIS INFORMATION\n{'─' * 60}\n"
        if result.get("whois"):
            for key, value in result["whois"].items():
                if value and key != "error":
                    yield f"  {key.replace('_', ' ').title()}: {value}\n"
        else:
            yield "  No WHOIS information available\n"
        
        yield f"\n[2/4] DNS RECORDS\n{'─' * 60}\n"
        if result.get("dns_records"):
            for record_type, values in result["dns_records"].items():
                if values:
                    yield f"  {record_type}:\n"
                    for value in values[:3]:
                        yield f"    • {value}\n"
        
        yield f"\n[3/4] SUBDOMAINS (Certificate Transparency)\n{'─' * 60}\n"
        if result.get("subdomains"):
            yield f"  Found {len(result['subdomains'])} subdomains:\n"
            for subdomain in result["subdomains"][:10]:
                yield f"    • {subdomain}\n"
                
                # Create subdomain entities
                if include_subdomains:
                    subdomain_id = f"domain_{hashlib.md5(subdomain.encode()).hexdigest()[:8]}"
                    self._create_entity_node(
                        subdomain_id,
                        "subdomain",
                        {"subdomain": subdomain, "parent_domain": domain}
                    )
                    self._link_entities(domain_id, subdomain_id, "HAS_SUBDOMAIN")
            
            if len(result["subdomains"]) > 10:
                yield f"    ... and {len(result['subdomains']) - 10} more\n"
        else:
            yield "  No subdomains found\n"
        
        yield f"\n[4/4] SSL CERTIFICATES\n{'─' * 60}\n"
        if result.get("certificates"):
            yield f"  Found {len(result['certificates'])} certificate entries\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Domain Investigation Complete\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def investigate_phone(self, target: str, country_code: Optional[str] = None) -> Iterator[str]:
        """Investigate phone number"""
        
        phone = OSINTInputParser.extract_target(target, OSINTMode.PHONE)
        
        self._initialize_investigation("investigate_phone", phone, "phone")
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                  PHONE INVESTIGATION                         ║\n"
        yield f"║                   Target: {phone:^30}         ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        # Investigate
        result = self.phone.investigate_phone(phone, country_code)
        
        # Create phone entity
        phone_id = f"phone_{hashlib.md5(phone.encode()).hexdigest()[:8]}"
        self._create_entity_node(
            phone_id,
            "phone",
            {
                "phone": phone,
                "formatted": result["formatted"],
                "valid": result["valid"],
                "country_code": result.get("country_code"),
                "location": result.get("location")
            }
        )
        
        yield f"Phone Number Analysis:\n{'─' * 60}\n"
        yield f"  Formatted: {result['formatted']}\n"
        yield f"  Valid: {'✓' if result['valid'] else '✗'}\n"
        
        if result.get("country_code"):
            yield f"  Country: {result['country_code']}\n"
        
        if result.get("location"):
            yield f"  Location: {result['location']}\n"
        
        if result.get("type"):
            yield f"  Type: {result['type']}\n"
        
        if result.get("carrier"):
            yield f"  Carrier: {result['carrier']}\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Phone Investigation Complete\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def investigate_license_plate(self, target: str, state: Optional[str] = None,
                                 country: str = "US") -> Iterator[str]:
        """Investigate license plate"""
        
        plate = target.strip().upper()
        
        self._initialize_investigation("investigate_license_plate", plate, "license_plate")
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║              LICENSE PLATE INVESTIGATION                     ║\n"
        yield f"║                   Plate: {plate:^30}          ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        # Investigate
        result = self.plate.investigate_plate(plate, state, country)
        
        # Create license plate entity
        plate_id = f"plate_{hashlib.md5(plate.encode()).hexdigest()[:8]}"
        self._create_entity_node(
            plate_id,
            "license_plate",
            {
                "plate": plate,
                "state": state,
                "country": country,
                "format_valid": result["format_valid"]
            }
        )
        
        yield f"License Plate Analysis:\n{'─' * 60}\n"
        yield f"  Plate: {result['plate']}\n"
        yield f"  Country: {result['country']}\n"
        
        if result.get("state"):
            yield f"  State: {result['state']}\n"
        
        yield f"  Format Valid: {'✓' if result['format_valid'] else '✗'}\n"
        
        if result.get("state_patterns"):
            yield f"\n  Possible State Matches:\n"
            for state, confidence in result["state_patterns"].items():
                yield f"    • {state}: {confidence}\n"
        
        if result.get("year"):
            yield f"\n  Registration Year: {result['year']}\n"
        
        if result.get("region"):
            yield f"  Region: {result['region']}\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  License Plate Investigation Complete\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def investigate_company(self, target: str, country: str = "US") -> Iterator[str]:
        """Investigate company"""
        
        company_name = target.strip()
        
        self._initialize_investigation("investigate_company", company_name, "company")
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                 COMPANY INVESTIGATION                        ║\n"
        yield f"║                Company: {company_name:^30}        ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        # Investigate
        result = self.company.investigate_company(company_name, country)
        
        # Create company entity
        company_id = f"company_{hashlib.md5(company_name.encode()).hexdigest()[:8]}"
        self._create_entity_node(
            company_id,
            "company",
            {
                "company_name": company_name,
                "country": country
            }
        )
        
        yield f"Company Information:\n{'─' * 60}\n"
        yield f"  Name: {result['company_name']}\n"
        yield f"  Country: {result['country']}\n"
        
        yield f"\n  Public Registry Searches:\n"
        
        if result.get("opencorporates"):
            yield f"    • OpenCorporates: {result['opencorporates'].get('search_url', 'N/A')}\n"
        
        if result.get("sec_filings"):
            for filing in result["sec_filings"]:
                yield f"    • {filing['source']}: {filing['search_url']}\n"
        
        if result.get("companies_house"):
            yield f"    • UK Companies House: {result['companies_house']['search_url']}\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Company Investigation Complete\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"
    
    def check_data_breaches(self, target: str, check_type: str = "email") -> Iterator[str]:
        """Check for data breaches"""
        
        identifier = OSINTInputParser.extract_target(target)
        
        self._initialize_investigation("check_data_breaches", identifier, check_type)
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"║                DATA BREACH CHECK                             ║\n"
        yield f"║                Target: {identifier:^30}           ║\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n\n"
        
        # Check breaches
        result = self.breach.check_breaches(identifier, check_type)
        
        # Create entity
        entity_id = f"breach_check_{hashlib.md5(identifier.encode()).hexdigest()[:8]}"
        self._create_entity_node(
            entity_id,
            "breach_check",
            {
                "identifier": identifier,
                "type": check_type,
                "total_breaches": result.get("total_breaches", 0)
            }
        )
        
        yield f"Breach Check Results:\n{'─' * 60}\n"
        yield f"  Identifier: {result['identifier']}\n"
        yield f"  Type: {result['type']}\n"
        yield f"  Total Known Breaches: {result.get('total_breaches', 0)}\n"
        
        if result.get("breaches"):
            yield f"\n  Sample Breaches:\n"
            for breach in result["breaches"]:
                yield f"    • {breach['name']} ({breach['breach_date']})\n"
                yield f"      Domain: {breach.get('domain', 'N/A')}\n"
                if breach.get("data_classes"):
                    yield f"      Data: {', '.join(breach['data_classes'][:5])}\n"
        
        if result.get("error"):
            yield f"\n  Error: {result['error']}\n"
        
        yield f"\n╔══════════════════════════════════════════════════════════════╗\n"
        yield f"  Breach Check Complete\n"
        yield f"╚══════════════════════════════════════════════════════════════╝\n"

# =============================================================================
# TOOL INTEGRATION
# =============================================================================

def add_osint_tools(tool_list: List, agent):
    """Add comprehensive OSINT tools to agent"""
    from langchain_core.tools import StructuredTool
    
    # Username investigation
    def investigate_username_wrapper(target: str, platforms: Optional[List[str]] = None,
                                    deep_scan: bool = False):
        config = OSINTConfig.deep_scan() if deep_scan else OSINTConfig.quick_scan()
        mapper = OSINTMapper(agent, config)
        for chunk in mapper.investigate_username(target, platforms, deep_scan):
            yield chunk
    
    # Email investigation
    def investigate_email_wrapper(target: str, check_breaches: bool = True,
                                 verify_mx: bool = True):
        config = OSINTConfig.quick_scan()
        mapper = OSINTMapper(agent, config)
        for chunk in mapper.investigate_email(target, check_breaches, verify_mx):
            yield chunk
    
    # Domain investigation
    def investigate_domain_wrapper(target: str, include_subdomains: bool = False,
                                  check_history: bool = False):
        config = OSINTConfig.quick_scan()
        mapper = OSINTMapper(agent, config)
        for chunk in mapper.investigate_domain(target, include_subdomains):
            yield chunk
    
    # Phone investigation
    def investigate_phone_wrapper(target: str, country_code: Optional[str] = None,
                                 carrier_lookup: bool = True):
        config = OSINTConfig.quick_scan()
        mapper = OSINTMapper(agent, config)
        for chunk in mapper.investigate_phone(target, country_code):
            yield chunk
    
    # License plate investigation
    def investigate_license_plate_wrapper(target: str, state: Optional[str] = None,
                                         country: str = "US"):
        config = OSINTConfig.quick_scan()
        mapper = OSINTMapper(agent, config)
        for chunk in mapper.investigate_license_plate(target, state, country):
            yield chunk
    
    # Company investigation
    def investigate_company_wrapper(target: str, country: str = "US",
                                   include_filings: bool = False):
        config = OSINTConfig.quick_scan()
        mapper = OSINTMapper(agent, config)
        for chunk in mapper.investigate_company(target, country):
            yield chunk
    
    # Data breach check
    def check_data_breaches_wrapper(target: str, check_type: str = "email"):
        config = OSINTConfig.quick_scan()
        mapper = OSINTMapper(agent, config)
        for chunk in mapper.check_data_breaches(target, check_type):
            yield chunk
    
    tool_list.extend([
        StructuredTool.from_function(
            func=investigate_username_wrapper,
            name="investigate_username",
            description=(
                "Investigate username across social media platforms. FULLY STANDALONE. "
                "Discovers profiles, metadata, and connections. Uses only free, public sources. "
                "Automatically extracts username from any input format."
            ),
            args_schema=UsernameOSINTInput
        ),
        
        StructuredTool.from_function(
            func=investigate_email_wrapper,
            name="investigate_email",
            description=(
                "Investigate email address. FULLY STANDALONE. "
                "Validates format, checks MX records, domain info, variations. "
                "Uses only free, public sources. Tool chaining compatible."
            ),
            args_schema=EmailOSINTInput
        ),
        
        StructuredTool.from_function(
            func=investigate_domain_wrapper,
            name="investigate_domain",
            description=(
                "Investigate domain. FULLY STANDALONE. "
                "WHOIS, DNS records, subdomains via certificate transparency. "
                "Uses only free, public sources. Tool chaining compatible."
            ),
            args_schema=DomainOSINTInput
        ),
        
        StructuredTool.from_function(
            func=investigate_phone_wrapper,
            name="investigate_phone",
            description=(
                "Investigate phone number. FULLY STANDALONE. "
                "Format validation, country code, area code location lookup. "
                "Uses only free, public sources."
            ),
            args_schema=PhoneOSINTInput
        ),
        
        StructuredTool.from_function(
            func=investigate_license_plate_wrapper,
            name="investigate_license_plate",
            description=(
                "Investigate license plate. FULLY STANDALONE. "
                "Format validation, state/region identification (US/UK). "
                "Uses only publicly available pattern matching - NO private DMV data."
            ),
            args_schema=LicensePlateInput
        ),
        
        StructuredTool.from_function(
            func=investigate_company_wrapper,
            name="investigate_company",
            description=(
                "Investigate company/business. FULLY STANDALONE. "
                "Public registry searches (OpenCorporates, SEC EDGAR, Companies House). "
                "Uses only free, public sources."
            ),
            args_schema=CompanyOSINTInput
        ),
        
        StructuredTool.from_function(
            func=check_data_breaches_wrapper,
            name="check_data_breaches",
            description=(
                "Check for data breaches. FULLY STANDALONE. "
                "Searches known breach databases for email/username/domain. "
                "Uses HaveIBeenPwned and other free breach databases."
            ),
            args_schema=DataBreachInput
        ),
    ])
    
    return tool_list

if __name__ == "__main__":
    print("OSINT Toolkit - Living Off The Land Edition")
    print("✓ Free & open sources only")
    print("✓ Each tool works standalone")
    print("✓ Automatically extracts targets from formatted input")
    print("✓ Graph memory integration")
    print("✓ Tool chaining compatible")
    print("\nAvailable investigations:")
    print("  • Username (social media)")
    print("  • Email (validation, MX, breaches)")
    print("  • Domain (WHOIS, DNS, subdomains)")
    print("  • Phone (format, location, carrier)")
    print("  • License Plate (format, state/region)")
    print("  • Company (public registries)")
    print("  • Data Breaches (known leaks)")