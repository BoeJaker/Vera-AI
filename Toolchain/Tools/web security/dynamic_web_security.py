"""
Dynamic OWASP & CWE Database Integration Module

A standalone module that fetches live OWASP and CWE databases and constructs
security tests dynamically from the latest vulnerability information.
"""

import requests
import json
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from datetime import datetime
import logging
import sqlite3
from pathlib import Path
import hashlib
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CWEItem:
    """Data class for CWE items."""
    id: str
    name: str
    description: str
    extended_description: str
    likelihood: str
    severity: str
    common_consequences: List[str]
    examples: List[Dict[str, str]]
    mitigation: str
    references: List[str]
    related_weaknesses: List[str]
    last_updated: datetime

@dataclass
class OWASPItem:
    """Data class for OWASP items."""
    id: str
    name: str
    description: str
    risks: List[str]
    examples: List[Dict[str, str]]
    prevention: List[str]
    references: List[str]
    related_cwe: List[str]
    last_updated: datetime

@dataclass
class SecurityTest:
    """Data class for security tests."""
    test_id: str
    name: str
    description: str
    test_type: str
    target: str
    severity: str
    cwe_ids: List[str]
    owasp_refs: List[str]
    mitigation: str
    references: List[str]
    payloads: List[str]
    validation_patterns: List[str]

class OWASPCWEDatabase:
    """Class to fetch and manage OWASP and CWE databases."""
    
    def __init__(self, cache_dir: str = ".security_cache", cache_ttl: int = 86400):
        self.cache_dir = Path(cache_dir)
        self.cache_ttl = cache_ttl  # 24 hours in seconds
        self.cwe_data: Dict[str, CWEItem] = {}
        self.owasp_data: Dict[str, OWASPItem] = {}
        self.security_tests: Dict[str, SecurityTest] = {}
        
        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(exist_ok=True)
    
    def fetch_cwe_database(self, use_cache: bool = True) -> bool:
        """
        Fetch the CWE database from MITRE's official source.
        
        Args:
            use_cache: Whether to use cached data if available and not expired
            
        Returns:
            bool: True if successful, False otherwise
        """
        cwe_url = "https://cwe.mitre.org/data/xml/cwec_latest.xml"
        cache_file = self.cache_dir / "cwe_latest.xml"
        
        # Check if we can use cached data
        if use_cache and cache_file.exists():
            cache_age = time.time() - cache_file.stat().st_mtime
            if cache_age < self.cache_ttl:
                logger.info("Using cached CWE data")
                return self.parse_cwe_xml(cache_file.read_text())
        
        try:
            logger.info("Fetching latest CWE data from MITRE")
            response = requests.get(cwe_url, timeout=30)
            response.raise_for_status()
            
            # Save to cache
            cache_file.write_text(response.text)
            
            # Parse the XML
            return self.parse_cwe_xml(response.text)
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch CWE data: {e}")
            if cache_file.exists():
                logger.warning("Falling back to cached CWE data")
                return self.parse_cwe_xml(cache_file.read_text())
            return False
        except Exception as e:
            logger.error(f"Error processing CWE data: {e}")
            return False
    
    def parse_cwe_xml(self, xml_content: str) -> bool:
        """
        Parse CWE XML data.
        
        Args:
            xml_content: The XML content to parse
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            root = ET.fromstring(xml_content)
            namespace = {'cwe': 'http://cwe.mitre.org/cwe-6'}
            
            for weakness in root.findall('.//cwe:Weakness', namespace):
                # Extract basic information
                cwe_id = weakness.get('ID')
                name = weakness.find('cwe:Name', namespace)
                description = weakness.find('cwe:Description', namespace)
                
                if not all([cwe_id, name, description]):
                    continue
                
                # Extract extended description
                extended_desc = weakness.find('cwe:Extended_Description', namespace)
                extended_description = extended_desc.text if extended_desc is not None else ""
                
                # Extract likelihood and severity
                likelihood = "Unknown"
                severity = "Unknown"
                for likelihood_elt in weakness.findall('.//cwe:Likelihood_Of_Exploit', namespace):
                    likelihood = likelihood_elt.text or "Unknown"
                
                # Extract common consequences
                consequences = []
                for consequence in weakness.findall('.//cwe:Common_Consequence', namespace):
                    scope = consequence.find('cwe:Scope', namespace)
                    impact = consequence.find('cwe:Impact', namespace)
                    if scope is not None and impact is not None:
                        consequences.append(f"{scope.text}: {impact.text}")
                
                # Extract examples
                examples = []
                for example in weakness.findall('.//cwe:Example', namespace):
                    example_text = example.find('cwe:Example_Text', namespace)
                    if example_text is not None and example_text.text:
                        examples.append({
                            "description": "Example from CWE database",
                            "code": example_text.text
                        })
                
                # Extract mitigation
                mitigation = ""
                for mitigation_elt in weakness.findall('.//cwe:Mitigation', namespace):
                    mitigation_desc = mitigation_elt.find('cwe:Description', namespace)
                    if mitigation_desc is not None and mitigation_desc.text:
                        mitigation += mitigation_desc.text + "\n"
                
                # Extract references
                references = []
                for ref in weakness.findall('.//cwe:Reference', namespace):
                    ref_url = ref.get('External_Reference_ID')
                    if ref_url:
                        references.append(f"https://cwe.mitre.org/data/definitions/{cwe_id}.html")
                
                # Extract related weaknesses
                related_weaknesses = []
                for related in weakness.findall('.//cwe:Related_Weakness', namespace):
                    related_id = related.get('CWE_ID')
                    if related_id:
                        related_weaknesses.append(related_id)
                
                # Create CWE item
                self.cwe_data[cwe_id] = CWEItem(
                    id=cwe_id,
                    name=name.text,
                    description=description.text,
                    extended_description=extended_description,
                    likelihood=likelihood,
                    severity=severity,
                    common_consequences=consequences,
                    examples=examples,
                    mitigation=mitigation,
                    references=references,
                    related_weaknesses=related_weaknesses,
                    last_updated=datetime.now()
                )
            
            logger.info(f"Successfully parsed {len(self.cwe_data)} CWE entries")
            return True
            
        except Exception as e:
            logger.error(f"Error parsing CWE XML: {e}")
            return False
    
    def fetch_owasp_database(self, use_cache: bool = True) -> bool:
        """
        Fetch OWASP data from official sources.
        
        Args:
            use_cache: Whether to use cached data if available and not expired
            
        Returns:
            bool: True if successful, False otherwise
        """
        # OWASP Top 10 GitHub repository
        owasp_urls = {
            "top10": "https://raw.githubusercontent.com/OWASP/Top10/master/2021/en/0x01-top10.md",
            "api_top10": "https://raw.githubusercontent.com/OWASP/API-Security/master/2023/en/0x0intro.md",
            "testing_guide": "https://raw.githubusercontent.com/OWASP/wstg/master/document/4-Web_Application_Security_Testing/README.md"
        }
        
        cache_file = self.cache_dir / "owasp_data.json"
        
        # Check if we can use cached data
        if use_cache and cache_file.exists():
            cache_age = time.time() - cache_file.stat().st_mtime
            if cache_age < self.cache_ttl:
                logger.info("Using cached OWASP data")
                try:
                    cached_data = json.loads(cache_file.read_text())
                    self.owasp_data = {
                        k: OWASPItem(**v) for k, v in cached_data.items()
                    }
                    return True
                except:
                    logger.warning("Failed to load cached OWASP data")
        
        try:
            logger.info("Fetching OWASP data from various sources")
            
            # Try to fetch OWASP Top 10 data
            try:
                response = requests.get(owasp_urls["top10"], timeout=30)
                if response.status_code == 200:
                    self.parse_owasp_top10(response.text)
            except:
                logger.warning("Failed to fetch OWASP Top 10 data")
            
            # Try to fetch API Security Top 10 data
            try:
                response = requests.get(owasp_urls["api_top10"], timeout=30)
                if response.status_code == 200:
                    self.parse_owasp_api_top10(response.text)
            except:
                logger.warning("Failed to fetch OWASP API Security Top 10 data")
            
            # If we have data, save to cache
            if self.owasp_data:
                cache_data = {
                    k: {
                        "id": v.id,
                        "name": v.name,
                        "description": v.description,
                        "risks": v.risks,
                        "examples": v.examples,
                        "prevention": v.prevention,
                        "references": v.references,
                        "related_cwe": v.related_cwe,
                        "last_updated": v.last_updated.isoformat()
                    } for k, v in self.owasp_data.items()
                }
                cache_file.write_text(json.dumps(cache_data, indent=2))
                return True
            else:
                logger.warning("No OWASP data was fetched")
                return False
                
        except Exception as e:
            logger.error(f"Error fetching OWASP data: {e}")
            return False
    
    def parse_owasp_top10(self, content: str):
        """Parse OWASP Top 10 content."""
        # This is a simplified parser - in a real implementation, you'd need
        # a more sophisticated approach to parse the markdown content
        lines = content.split('\n')
        current_category = None
        
        for line in lines:
            if line.startswith('### A0'):
                # This is a category header
                parts = line.split(':', 1)
                if len(parts) == 2:
                    category_id = parts[0].replace('###', '').strip()
                    category_name = parts[1].strip()
                    
                    current_category = category_id
                    self.owasp_data[category_id] = OWASPItem(
                        id=category_id,
                        name=category_name,
                        description="",
                        risks=[],
                        examples=[],
                        prevention=[],
                        references=[f"https://owasp.org/Top10/{category_id}/"],
                        related_cwe=[],
                        last_updated=datetime.now()
                    )
            
            elif current_category and line.startswith('**Description**:'):
                desc = line.replace('**Description**:', '').strip()
                self.owasp_data[current_category].description = desc
    
    def parse_owasp_api_top10(self, content: str):
        """Parse OWASP API Security Top 10 content."""
        # Similar to parse_owasp_top10 but for API security
        lines = content.split('\n')
        current_category = None
        
        for line in lines:
            if line.startswith('### API'):
                # This is an API security category header
                parts = line.split(':', 1)
                if len(parts) == 2:
                    category_id = parts[0].replace('###', '').strip()
                    category_name = parts[1].strip()
                    
                    current_category = category_id
                    self.owasp_data[category_id] = OWASPItem(
                        id=category_id,
                        name=category_name,
                        description="",
                        risks=[],
                        examples=[],
                        prevention=[],
                        references=[f"https://owasp.org/API-Security/{category_id}/"],
                        related_cwe=[],
                        last_updated=datetime.now()
                    )
    
    def fetch_nvd_data(self, cwe_id: str) -> List[Dict]:
        """
        Fetch CVE data from NVD for a specific CWE.
        
        Args:
            cwe_id: The CWE ID to fetch CVEs for
            
        Returns:
            List of CVE data dictionaries
        """
        nvd_url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cweId={cwe_id}"
        cache_file = self.cache_dir / f"nvd_{cwe_id}.json"
        
        # Check cache first
        if cache_file.exists():
            cache_age = time.time() - cache_file.stat().st_mtime
            if cache_age < self.cache_ttl:
                try:
                    return json.loads(cache_file.read_text())
                except:
                    pass
        
        try:
            logger.info(f"Fetching NVD data for {cwe_id}")
            response = requests.get(nvd_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            cves = data.get('vulnerabilities', [])
            
            # Cache the results
            cache_file.write_text(json.dumps(cves, indent=2))
            
            return cves
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch NVD data for {cwe_id}: {e}")
            return []
    
    def generate_security_tests(self):
        """Generate security tests from CWE and OWASP data."""
        logger.info("Generating security tests from CWE and OWASP data")
        
        for cwe_id, cwe_item in self.cwe_data.items():
            # Create test ID
            test_id = f"cwe_{cwe_id}"
            
            # Determine test type based on CWE name and description
            test_type = self.determine_test_type(cwe_item.name, cwe_item.description)
            
            # Generate payloads from examples
            payloads = []
            for example in cwe_item.examples:
                if 'code' in example:
                    payloads.append(example['code'])
            
            # If no examples, generate generic payloads based on CWE type
            if not payloads:
                payloads = self.generate_generic_payloads(test_type, cwe_id)
            
            # Create validation patterns
            validation_patterns = self.generate_validation_patterns(test_type)
            
            # Find related OWASP categories
            owasp_refs = self.find_related_owasp(cwe_id)
            
            # Create the security test
            self.security_tests[test_id] = SecurityTest(
                test_id=test_id,
                name=f"CWE-{cwe_id}: {cwe_item.name}",
                description=cwe_item.description,
                test_type=test_type,
                target="input_fields",  # Default target
                severity=cwe_item.severity,
                cwe_ids=[cwe_id],
                owasp_refs=owasp_refs,
                mitigation=cwe_item.mitigation,
                references=cwe_item.references,
                payloads=payloads,
                validation_patterns=validation_patterns
            )
        
        logger.info(f"Generated {len(self.security_tests)} security tests")
    
    def determine_test_type(self, name: str, description: str) -> str:
        """Determine test type based on CWE name and description."""
        name_lower = name.lower()
        desc_lower = description.lower()
        
        if any(x in name_lower or x in desc_lower for x in ['xss', 'cross-site', 'script']):
            return "xss"
        elif any(x in name_lower or x in desc_lower for x in ['sql', 'injection']):
            return "sql_injection"
        elif any(x in name_lower or x in desc_lower for x in ['command', 'injection']):
            return "command_injection"
        elif any(x in name_lower or x in desc_lower for x in ['path', 'traversal', 'directory']):
            return "path_traversal"
        elif any(x in name_lower or x in desc_lower for x in ['buffer', 'overflow']):
            return "buffer_overflow"
        elif any(x in name_lower or x in desc_lower for x in ['access', 'control', 'authorization']):
            return "access_control"
        else:
            return "generic"
    
    def generate_generic_payloads(self, test_type: str, cwe_id: str) -> List[str]:
        """Generate generic payloads based on test type."""
        payloads = {
            "xss": [
                "<script>alert('XSS')</script>",
                "<img src=x onerror=alert('XSS')>",
                "javascript:alert('XSS')"
            ],
            "sql_injection": [
                "' OR '1'='1'--",
                "'; DROP TABLE users;--",
                "' UNION SELECT username, password FROM users--"
            ],
            "command_injection": [
                "; ls -la",
                "| cat /etc/passwd",
                "`id`"
            ],
            "path_traversal": [
                "../../../etc/passwd",
                "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
                "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd"
            ],
            "access_control": [
                "admin",
                "true",
                "1"
            ],
            "generic": [
                "test_payload",
                "${7*7}",
                "#{7*7}"
            ]
        }
        
        return payloads.get(test_type, payloads["generic"])
    
    def generate_validation_patterns(self, test_type: str) -> List[str]:
        """Generate validation patterns based on test type."""
        patterns = {
            "xss": [
                r"<script[^>]*>.*?</script>",
                r"javascript:",
                r"onerror=",
                r"onload="
            ],
            "sql_injection": [
                r"sql syntax",
                r"mysql_fetch",
                r"ora-",
                r"unclosed quotation"
            ],
            "command_injection": [
                r"command not found",
                r"permission denied",
                r"cannot execute"
            ],
            "path_traversal": [
                r"etc/passwd",
                r"root:",
                r"windows/system32"
            ],
            "access_control": [
                r"access denied",
                r"forbidden",
                r"unauthorized"
            ],
            "generic": [
                r"error",
                r"exception",
                r"invalid"
            ]
        }
        
        return patterns.get(test_type, patterns["generic"])
    
    def find_related_owasp(self, cwe_id: str) -> List[str]:
        """Find related OWASP categories for a CWE."""
        # This is a simplified mapping - in a real implementation, you'd want
        # a more sophisticated approach to map CWEs to OWASP categories
        cwe_owasp_mapping = {
            "79": ["A03:2021"],  # XSS -> Injection
            "89": ["A03:2021"],  # SQL Injection -> Injection
            "78": ["A03:2021"],  # Command Injection -> Injection
            "22": ["A01:2021"],  # Path Traversal -> Broken Access Control
            "287": ["A07:2021"], # Improper Authentication -> Identification and Authentication Failures
            "352": ["A01:2021"], # CSRF -> Broken Access Control
            "798": ["A07:2021"], # Hard-coded Credentials -> Identification and Authentication Failures
            "434": ["A08:2021"], # Unrestricted Upload -> Software and Data Integrity Failures
            "502": ["A08:2021"], # Deserialization -> Software and Data Integrity Failures
            "918": ["A08:2021"]  # SSRF -> Software and Data Integrity Failures
        }
        
        return cwe_owasp_mapping.get(cwe_id, [])
    
    def get_test(self, test_id: str) -> Optional[SecurityTest]:
        """Get a security test by ID."""
        return self.security_tests.get(test_id)
    
    def get_tests_by_type(self, test_type: str) -> List[SecurityTest]:
        """Get all security tests of a specific type."""
        return [test for test in self.security_tests.values() if test.test_type == test_type]
    
    def get_tests_by_severity(self, severity: str) -> List[SecurityTest]:
        """Get all security tests with a specific severity."""
        return [test for test in self.security_tests.values() if test.severity.lower() == severity.lower()]
    
    def get_cwe(self, cwe_id: str) -> Optional[CWEItem]:
        """Get a CWE item by ID."""
        return self.cwe_data.get(cwe_id)
    
    def get_owasp(self, owasp_id: str) -> Optional[OWASPItem]:
        """Get an OWASP item by ID."""
        return self.owasp_data.get(owasp_id)
    
    def search_tests(self, query: str) -> List[SecurityTest]:
        """Search security tests by query."""
        query_lower = query.lower()
        results = []
        
        for test in self.security_tests.values():
            if (query_lower in test.name.lower() or 
                query_lower in test.description.lower() or
                any(query_lower in ref.lower() for ref in test.references) or
                any(query_lower in mit.lower() for mit in test.mitigation)):
                results.append(test)
        
        return results

# Example usage
if __name__ == "__main__":
    # Create database instance
    db = OWASPCWEDatabase()
    
    # Fetch CWE and OWASP data
    if db.fetch_cwe_database() and db.fetch_owasp_database():
        print(f"Successfully loaded {len(db.cwe_data)} CWE entries")
        print(f"Successfully loaded {len(db.owasp_data)} OWASP entries")
        
        # Generate security tests
        db.generate_security_tests()
        print(f"Generated {len(db.security_tests)} security tests")
        
        # Example: Get a specific test
        xss_test = db.get_test("cwe_79")
        if xss_test:
            print(f"\nXSS Test: {xss_test.name}")
            print(f"Payloads: {xss_test.payloads[:3]}")  # Show first 3 payloads
        
        # Example: Search for tests
        injection_tests = db.search_tests("injection")
        print(f"\nFound {len(injection_tests)} injection-related tests")
        
        # Example: Get CWE details
        cwe_89 = db.get_cwe("89")
        if cwe_89:
            print(f"\nCWE-89: {cwe_89.name}")
            print(f"Description: {cwe_89.description[:100]}...")  # First 100 chars
        
    else:
        print("Failed to load CWE or OWASP data")