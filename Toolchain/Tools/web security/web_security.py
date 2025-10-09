"""
Dynamic OWASP & CWE Security Testing Framework

A security testing tool that dynamically constructs tests using examples 
from OWASP and CWE databases for comprehensive vulnerability detection.
"""

from typing import Dict, List, Optional, Any, Tuple, Type, Set
from pydantic import BaseModel, Field
import re
import asyncio
import aiohttp
from urllib.parse import urlparse, quote, parse_qs
import json
import hashlib
from datetime import datetime
from langchain.tools import BaseTool
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import random
import html
import logging
import sqlite3
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecurityTestTemplate(BaseModel):
    """Model for security test templates."""
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
    payload_generator: Any  # Function to generate payloads
    result_validator: Any   # Function to validate results

class TestResult(BaseModel):
    """Model for test results."""
    test_id: str
    test_name: str
    target_url: str
    payload_used: str
    result: str  # "vulnerable", "not_vulnerable", "inconclusive"
    evidence: str
    severity: str
    cwe_ids: List[str]
    owasp_refs: List[str]
    timestamp: datetime = Field(default_factory=datetime.now)

class DynamicSecurityTester:
    """Dynamic security tester that constructs tests from OWASP and CWE databases."""
    
    def __init__(self, cwe_db_path: str = None, owasp_db_path: str = None):
        self.cwe_db = {}
        self.owasp_db = {}
        self.test_templates: Dict[str, SecurityTestTemplate] = {}
        self.session = None
        
        # Load databases
        self.load_cwe_database(cwe_db_path)
        self.load_owasp_database(owasp_db_path)
        
        # Generate test templates
        self.generate_test_templates()
    
    def load_cwe_database(self, db_path: str = None):
        """Load CWE database from file or online source."""
        try:
            if db_path and Path(db_path).exists():
                # Load from local file
                with open(db_path, 'r') as f:
                    self.cwe_db = json.load(f)
                logger.info(f"Loaded CWE database from {db_path}")
            else:
                # Try to load from online source (simplified example)
                try:
                    # In a real implementation, this would fetch from MITRE's CWE database
                    response = requests.get("https://cwe.mitre.org/data/xml/cwec_latest.xml", timeout=10)
                    if response.status_code == 200:
                        print(f"Loaded CWE database from online source\n{response.content}")
                        self.parse_cwe_xml(response.content)
                    else:
                        self.load_default_cwe_data()
                except:
                    self.load_default_cwe_data()
        except Exception as e:
            logger.error(f"Error loading CWE database: {e}")
            self.load_default_cwe_data()
    
    def load_default_cwe_data(self):
        """Load default CWE data as fallback."""
        # Simplified example - in a real implementation, this would be more comprehensive
        self.cwe_db = {
            "79": {
                "id": "79",
                "name": "Cross-site Scripting",
                "description": "Improper neutralization of input during web page generation",
                "extended_description": "The software does not neutralize or incorrectly neutralizes user-controllable input before it is placed in output that is used as a web page that is served to other users.",
                "likelihood": "High",
                "severity": "High",
                "common_consequences": ["Execute unauthorized code or commands", "Bypass security controls"],
                "examples": [
                    {"description": "Simple XSS in comment field", "code": "<script>alert('XSS')</script>"},
                    {"description": "XSS using img tag", "code": "<img src=x onerror=alert('XSS')>"},
                    {"description": "XSS using JavaScript URI", "code": "javascript:alert('XSS')"}
                ],
                "mitigation": "Use context-specific output encoding, validate input, and implement Content Security Policy.",
                "references": [
                    "https://cwe.mitre.org/data/definitions/79.html",
                    "https://owasp.org/www-community/attacks/xss/"
                ]
            },
            "89": {
                "id": "89",
                "name": "SQL Injection",
                "description": "Improper neutralization of special elements used in an SQL command",
                "extended_description": "The software constructs all or part of an SQL command using externally-influenced input but does not neutralize special elements that could modify the intended SQL command.",
                "likelihood": "Medium",
                "severity": "High",
                "common_consequences": ["Read, modify, or delete database data", "Bypass authentication"],
                "examples": [
                    {"description": "Basic SQL injection", "code": "' OR '1'='1'--"},
                    {"description": "Union-based SQL injection", "code": "' UNION SELECT username, password FROM users--"},
                    {"description": "Time-based blind SQL injection", "code": "' OR SLEEP(5)--"}
                ],
                "mitigation": "Use parameterized queries, stored procedures, ORM frameworks, and input validation.",
                "references": [
                    "https://cwe.mitre.org/data/definitions/89.html",
                    "https://owasp.org/www-community/attacks/SQL_Injection"
                ]
            },
            # Additional CWE entries would be added here
        }
        logger.info("Loaded default CWE data")
    
    def parse_cwe_xml(self, xml_content):
        """Parse CWE XML data (simplified example)."""
        try:
            root = ET.fromstring(xml_content)
            # In a real implementation, this would parse the full CWE XML structure
            for weakness in root.findall('.//Weakness'):
                cwe_id = weakness.get('ID')
                name = weakness.find('Name').text if weakness.find('Name') is not None else ""
                description = weakness.find('Description').text if weakness.find('Description') is not None else ""
                
                self.cwe_db[cwe_id] = {
                    "id": cwe_id,
                    "name": name,
                    "description": description,
                    "examples": [],
                    "mitigation": "",
                    "references": []
                }
            
            logger.info(f"Parsed {len(self.cwe_db)} CWE entries from XML")
        except Exception as e:
            logger.error(f"Error parsing CWE XML: {e}")
            self.load_default_cwe_data()
    
    def load_owasp_database(self, db_path: str = None):
        """Load OWASP database from file or online source."""
        try:
            if db_path and Path(db_path).exists():
                # Load from local file
                with open(db_path, 'r') as f:
                    self.owasp_db = json.load(f)
                logger.info(f"Loaded OWASP database from {db_path}")
            else:
                # Try to load from online source (simplified example)
                try:
                    # In a real implementation, this would fetch from OWASP resources
                    response = requests.get("https://raw.githubusercontent.com/OWASP/owasp-mstg/master/Document/0x04b-Mobile-App-Testing-Guide.json", timeout=10)
                    if response.status_code == 200:
                        self.owasp_db = response.json()
                    else:
                        self.load_default_owasp_data()
                except:
                    self.load_default_owasp_data()
        except Exception as e:
            logger.error(f"Error loading OWASP database: {e}")
            self.load_default_owasp_data()
    
    def load_default_owasp_data(self):
        """Load default OWASP data as fallback."""
        # Simplified example - in a real implementation, this would be more comprehensive
        self.owasp_db = {
            "A03:2021": {
                "id": "A03:2021",
                "name": "Injection",
                "description": "Injection flaws allow attackers to relay malicious code through an application to another system.",
                "risks": ["Data loss", "Data corruption", "Disclosure of sensitive information", "DoS"],
                "examples": [
                    {"type": "SQL Injection", "example": "' OR '1'='1'--"},
                    {"type": "OS Command Injection", "example": "; ls -la"},
                    {"type": "LDAP Injection", "example": "*)(uid=*))(|(uid=*"}
                ],
                "prevention": [
                    "Use safe APIs that avoid interpreters entirely",
                    "Use parameterized interfaces",
                    "Enforce least privilege"
                ],
                "references": [
                    "https://owasp.org/Top10/A03_2021-Injection/",
                    "https://cheatsheetseries.owasp.org/cheatsheets/Injection_Prevention_Cheat_Sheet.html"
                ]
            },
            "A01:2021": {
                "id": "A01:2021",
                "name": "Broken Access Control",
                "description": "Access control enforces policy such that users cannot act outside of their intended permissions.",
                "risks": ["Unauthorized information disclosure", "Modification or destruction of data", "Business function abuse"],
                "examples": [
                    {"type": "Vertical privilege escalation", "example": "Changing user role parameter to admin"},
                    {"type": "Horizontal privilege escalation", "example": "Accessing another user's data by modifying ID parameter"},
                    {"type": "Bypassing authorization", "example": "Accessing API endpoints without proper authentication"}
                ],
                "prevention": [
                    "Implement proper authorization checks",
                    "Deny by default",
                    "Enforce record ownership"
                ],
                "references": [
                    "https://owasp.org/Top10/A01_2021-Broken_Access_Control/",
                    "https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html"
                ]
            },
            # Additional OWASP entries would be added here
        }
        logger.info("Loaded default OWASP data")
    
    def generate_test_templates(self):
        """Generate test templates from CWE and OWASP databases."""
        # Generate tests from CWE database
        for cwe_id, cwe_data in self.cwe_db.items():
            if "examples" in cwe_data and cwe_data["examples"]:
                self.create_test_from_cwe(cwe_id, cwe_data)
        
        # Generate tests from OWASP database
        for owasp_id, owasp_data in self.owasp_db.items():
            if "examples" in owasp_data and owasp_data["examples"]:
                self.create_test_from_owasp(owasp_id, owasp_data)
        
        logger.info(f"Generated {len(self.test_templates)} test templates")
    
    def create_test_from_cwe(self, cwe_id: str, cwe_data: Dict):
        """Create a test template from CWE data."""
        test_id = f"cwe_{cwe_id}"
        
        # Determine test type based on CWE name
        test_type = "generic"
        if "xss" in cwe_data["name"].lower() or "cross-site" in cwe_data["name"].lower():
            test_type = "xss"
        elif "sql" in cwe_data["name"].lower() and "injection" in cwe_data["name"].lower():
            test_type = "sql_injection"
        elif "injection" in cwe_data["name"].lower():
            test_type = "injection"
        elif "buffer" in cwe_data["name"].lower() and "overflow" in cwe_data["name"].lower():
            test_type = "buffer_overflow"
        
        # Create payload generator based on examples
        def payload_generator():
            examples = cwe_data.get("examples", [])
            if examples:
                return [example.get("code", "") for example in examples if "code" in example]
            return []
        
        # Create result validator based on test type
        def result_validator(response_text, payload):
            if test_type == "xss":
                # Check if payload is reflected without proper encoding
                if payload in response_text and not self.is_properly_encoded(payload, response_text):
                    return "vulnerable"
                return "not_vulnerable"
            elif test_type == "sql_injection":
                # Check for SQL error messages or unusual behavior
                sql_errors = [
                    "sql syntax", "mysql_fetch", "ora-", "postgresql",
                    "microsoft ole db", "incorrect syntax", "unclosed quotation"
                ]
                if any(error in response_text.lower() for error in sql_errors):
                    return "vulnerable"
                return "not_vulnerable"
            else:
                # Generic validation - check if payload is reflected
                if payload in response_text:
                    return "potentially_vulnerable"
                return "not_vulnerable"
        
        # Create the test template
        self.test_templates[test_id] = SecurityTestTemplate(
            test_id=test_id,
            name=f"CWE-{cwe_id}: {cwe_data['name']}",
            description=cwe_data.get("description", ""),
            test_type=test_type,
            target="input_fields",  # Default target
            severity=cwe_data.get("severity", "medium"),
            cwe_ids=[cwe_id],
            owasp_refs=[],
            mitigation=cwe_data.get("mitigation", ""),
            references=cwe_data.get("references", []),
            payload_generator=payload_generator,
            result_validator=result_validator
        )
    
    def create_test_from_owasp(self, owasp_id: str, owasp_data: Dict):
        """Create a test template from OWASP data."""
        test_id = f"owasp_{owasp_id.replace(':', '_')}"
        
        # Determine test type based on OWASP name
        test_type = "generic"
        if "injection" in owasp_data["name"].lower():
            test_type = "injection"
        elif "broken access" in owasp_data["name"].lower():
            test_type = "access_control"
        elif "cross-site" in owasp_data["name"].lower():
            test_type = "xss"
        
        # Create payload generator based on examples
        def payload_generator():
            examples = owasp_data.get("examples", [])
            if examples:
                return [example.get("example", "") for example in examples if "example" in example]
            return []
        
        # Create result validator based on test type
        def result_validator(response_text, payload):
            if test_type == "injection":
                # Check for injection patterns
                injection_indicators = [
                    "syntax error", "unexpected token", "command not found",
                    "permission denied", "access denied"
                ]
                if any(indicator in response_text.lower() for indicator in injection_indicators):
                    return "vulnerable"
                return "not_vulnerable"
            elif test_type == "access_control":
                # Check for access control bypass
                if "admin" in payload.lower() and "admin" in response_text.lower():
                    return "potentially_vulnerable"
                return "not_vulnerable"
            else:
                # Generic validation
                if payload in response_text:
                    return "potentially_vulnerable"
                return "not_vulnerable"
        
        # Create the test template
        self.test_templates[test_id] = SecurityTestTemplate(
            test_id=test_id,
            name=f"{owasp_id}: {owasp_data['name']}",
            description=owasp_data.get("description", ""),
            test_type=test_type,
            target="input_fields",  # Default target
            severity="high",  # OWASP Top 10 are generally high severity
            cwe_ids=[],
            owasp_refs=[owasp_id],
            mitigation="\n".join(owasp_data.get("prevention", [])),
            references=owasp_data.get("references", []),
            payload_generator=payload_generator,
            result_validator=result_validator
        )
    
    def is_properly_encoded(self, payload: str, response_text: str) -> bool:
        """Check if a payload is properly encoded in the response."""
        # Check if payload is HTML encoded
        encoded_payload = html.escape(payload)
        if encoded_payload in response_text:
            return True
        
        # Check if payload is URL encoded
        url_encoded_payload = quote(payload)
        if url_encoded_payload in response_text:
            return True
        
        # Check if only parts of the payload are reflected
        # This is a simple heuristic and might need refinement
        dangerous_chars = ["<", ">", "'", '"', "&", "/", "\\", "(", ")", ";"]
        for char in dangerous_chars:
            if char in payload and char in response_text:
                return False
        
        return True
    
    async def initialize_session(self):
        """Initialize aiohttp session."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def run_test(self, test_id: str, target_url: str, **kwargs) -> TestResult:
        """Run a specific test against a target URL."""
        await self.initialize_session()
        
        if test_id not in self.test_templates:
            return TestResult(
                test_id=test_id,
                test_name="Unknown Test",
                target_url=target_url,
                payload_used="",
                result="inconclusive",
                evidence=f"Test {test_id} not found",
                severity="unknown",
                cwe_ids=[],
                owasp_refs=[]
            )
        
        test_template = self.test_templates[test_id]
        payloads = test_template.payload_generator()
        
        if not payloads:
            return TestResult(
                test_id=test_id,
                test_name=test_template.name,
                target_url=target_url,
                payload_used="",
                result="inconclusive",
                evidence="No payloads generated for test",
                severity=test_template.severity,
                cwe_ids=test_template.cwe_ids,
                owasp_refs=test_template.owasp_refs
            )
        
        # Try each payload until we find a vulnerability or exhaust all payloads
        for payload in payloads:
            try:
                # Determine the test method based on test type
                if test_template.test_type in ["xss", "sql_injection", "injection"]:
                    result = await self.test_input_injection(target_url, payload, test_template)
                elif test_template.test_type == "access_control":
                    result = await self.test_access_control(target_url, payload, test_template)
                else:
                    result = await self.test_generic(target_url, payload, test_template)
                
                if result.result != "not_vulnerable":
                    return result
                    
            except Exception as e:
                logger.error(f"Error running test {test_id} with payload {payload}: {e}")
                continue
        
        # If no vulnerabilities found with any payload
        return TestResult(
            test_id=test_id,
            test_name=test_template.name,
            target_url=target_url,
            payload_used="Multiple payloads tested",
            result="not_vulnerable",
            evidence="No vulnerabilities detected with available payloads",
            severity=test_template.severity,
            cwe_ids=test_template.cwe_ids,
            owasp_refs=test_template.owasp_refs
        )
    
    async def test_input_injection(self, target_url: str, payload: str, test_template: SecurityTestTemplate) -> TestResult:
        """Test for input injection vulnerabilities."""
        # Try different injection points
        injection_points = [
            {"method": "GET", "params": {"input": payload}},
            {"method": "POST", "data": {"input": payload}},
            {"method": "GET", "params": {"q": payload}},
            {"method": "POST", "data": {"search": payload}},
            {"method": "GET", "params": {"id": payload}},
            {"method": "POST", "data": {"user_id": payload}},
        ]
        
        for point in injection_points:
            try:
                if point["method"] == "GET":
                    # Add payload as query parameter
                    parsed_url = urlparse(target_url)
                    query_params = parse_qs(parsed_url.query)
                    param_name = list(point["params"].keys())[0]
                    query_params[param_name] = point["params"][param_name]
                    
                    # Rebuild URL with query parameters
                    new_query = "&".join([f"{k}={v}" for k, v in query_params.items()])
                    test_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?{new_query}"
                    
                    async with self.session.get(test_url) as response:
                        response_text = await response.text()
                        result = test_template.result_validator(response_text, payload)
                        
                        if result != "not_vulnerable":
                            return TestResult(
                                test_id=test_template.test_id,
                                test_name=test_template.name,
                                target_url=test_url,
                                payload_used=payload,
                                result=result,
                                evidence=f"Payload reflected in response to GET parameter {param_name}",
                                severity=test_template.severity,
                                cwe_ids=test_template.cwe_ids,
                                owasp_refs=test_template.owasp_refs
                            )
                
                elif point["method"] == "POST":
                    # Send payload as POST data
                    async with self.session.post(target_url, data=point["data"]) as response:
                        response_text = await response.text()
                        result = test_template.result_validator(response_text, payload)
                        
                        if result != "not_vulnerable":
                            param_name = list(point["data"].keys())[0]
                            return TestResult(
                                test_id=test_template.test_id,
                                test_name=test_template.name,
                                target_url=target_url,
                                payload_used=payload,
                                result=result,
                                evidence=f"Payload reflected in response to POST parameter {param_name}",
                                severity=test_template.severity,
                                cwe_ids=test_template.cwe_ids,
                                owasp_refs=test_template.owasp_refs
                            )
                            
            except Exception as e:
                logger.error(f"Error testing injection point: {e}")
                continue
        
        # No vulnerability found with this payload
        return TestResult(
            test_id=test_template.test_id,
            test_name=test_template.name,
            target_url=target_url,
            payload_used=payload,
            result="not_vulnerable",
            evidence="Payload not reflected or properly encoded",
            severity=test_template.severity,
            cwe_ids=test_template.cwe_ids,
            owasp_refs=test_template.owasp_refs
        )
    
    async def test_access_control(self, target_url: str, payload: str, test_template: SecurityTestTemplate) -> TestResult:
        """Test for access control vulnerabilities."""
        # This is a simplified example - real access control testing would be more comprehensive
        try:
            # First, get the normal response
            async with self.session.get(target_url) as response:
                normal_response = await response.text()
            
            # Try to manipulate the URL with the payload
            parsed_url = urlparse(target_url)
            test_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}/{payload}"
            
            async with self.session.get(test_url) as response:
                manipulated_response = await response.text()
                
                # Check if we got a different response
                if normal_response != manipulated_response:
                    # Check if we might have bypassed access controls
                    if "admin" in payload.lower() and ("admin" in manipulated_response.lower() or response.status != 403):
                        return TestResult(
                            test_id=test_template.test_id,
                            test_name=test_template.name,
                            target_url=test_url,
                            payload_used=payload,
                            result="potentially_vulnerable",
                            evidence="Different response received when manipulating URL with admin payload",
                            severity=test_template.severity,
                            cwe_ids=test_template.cwe_ids,
                            owasp_refs=test_template.owasp_refs
                        )
        
        except Exception as e:
            logger.error(f"Error testing access control: {e}")
        
        return TestResult(
            test_id=test_template.test_id,
            test_name=test_template.name,
            target_url=target_url,
            payload_used=payload,
            result="not_vulnerable",
            evidence="No access control bypass detected",
            severity=test_template.severity,
            cwe_ids=test_template.cwe_ids,
            owasp_refs=test_template.owasp_refs
        )
    
    async def test_generic(self, target_url: str, payload: str, test_template: SecurityTestTemplate) -> TestResult:
        """Generic test for other vulnerability types."""
        try:
            # Try a simple GET request with the payload in a common parameter
            parsed_url = urlparse(target_url)
            test_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?input={payload}"
            
            async with self.session.get(test_url) as response:
                response_text = await response.text()
                result = test_template.result_validator(response_text, payload)
                
                if result != "not_vulnerable":
                    return TestResult(
                        test_id=test_template.test_id,
                        test_name=test_template.name,
                        target_url=test_url,
                        payload_used=payload,
                        result=result,
                        evidence="Payload reflected in response",
                        severity=test_template.severity,
                        cwe_ids=test_template.cwe_ids,
                        owasp_refs=test_template.owasp_refs
                    )
        
        except Exception as e:
            logger.error(f"Error running generic test: {e}")
        
        return TestResult(
            test_id=test_template.test_id,
            test_name=test_template.name,
            target_url=target_url,
            payload_used=payload,
            result="not_vulnerable",
            evidence="No vulnerability detected",
            severity=test_template.severity,
            cwe_ids=test_template.cwe_ids,
            owasp_refs=test_template.owasp_refs
        )
    
    async def run_all_tests(self, target_url: str, test_types: List[str] = None) -> List[TestResult]:
        """Run all available tests against a target URL."""
        results = []
        
        for test_id, test_template in self.test_templates.items():
            if test_types and test_template.test_type not in test_types:
                continue
                
            try:
                result = await self.run_test(test_id, target_url)
                results.append(result)
                
                # Add a small delay to avoid overwhelming the target
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error running test {test_id}: {e}")
                results.append(TestResult(
                    test_id=test_id,
                    test_name=test_template.name,
                    target_url=target_url,
                    payload_used="",
                    result="inconclusive",
                    evidence=f"Error running test: {str(e)}",
                    severity=test_template.severity,
                    cwe_ids=test_template.cwe_ids,
                    owasp_refs=test_template.owasp_refs
                ))
        
        return results
    
    def generate_report(self, results: List[TestResult]) -> str:
        """Generate a comprehensive security report."""
        if not results:
            return "No test results available."
        
        # Group results by severity
        by_severity = {}
        for result in results:
            if result.severity not in by_severity:
                by_severity[result.severity] = []
            by_severity[result.severity].append(result)
        
        # Generate report
        report = ["# Dynamic Security Assessment Report", ""]
        
        # Executive summary
        report.append("## Executive Summary")
        report.append("")
        report.append(f"Total tests executed: {len(results)}")
        
        vulnerable_tests = [r for r in results if r.result != "not_vulnerable"]
        report.append(f"Vulnerabilities found: {len(vulnerable_tests)}")
        
        for severity in ["critical", "high", "medium", "low"]:
            if severity in by_severity:
                count = len([r for r in by_severity[severity] if r.result != "not_vulnerable"])
                report.append(f"- {severity.title()} severity vulnerabilities: {count}")
        
        report.append("")
        
        # Detailed findings
        for severity in ["critical", "high", "medium", "low"]:
            if severity in by_severity:
                vuln_results = [r for r in by_severity[severity] if r.result != "not_vulnerable"]
                if vuln_results:
                    report.append(f"## {severity.title()} Severity Findings")
                    report.append("")
                    
                    for i, result in enumerate(vuln_results, 1):
                        report.append(f"### {i}. {result.test_name}")
                        report.append(f"**Test ID**: {result.test_id}")
                        report.append(f"**Target URL**: {result.target_url}")
                        report.append(f"**Payload Used**: `{result.payload_used}`")
                        report.append(f"**Result**: {result.result}")
                        report.append(f"**Evidence**: {result.evidence}")
                        if result.cwe_ids:
                            report.append(f"**CWE IDs**: {', '.join(result.cwe_ids)}")
                        if result.owasp_refs:
                            report.append(f"**OWASP References**: {', '.join(result.owasp_refs)}")
                        report.append(f"**Timestamp**: {result.timestamp}")
                        report.append("")
        
        # Test summary
        report.append("## Test Summary")
        report.append("")
        report.append("| Test ID | Test Name | Result | Severity |")
        report.append("|---------|-----------|--------|----------|")
        
        for result in results:
            status = "✅" if result.result == "not_vulnerable" else "❌" if result.result == "vulnerable" else "⚠️"
            report.append(f"| {result.test_id} | {result.test_name} | {status} | {result.severity} |")
        
        return "\n".join(report)

# LangChain Tool Integration
class DynamicSecurityScanInput(BaseModel):
    """Input for dynamic security scan."""
    target_url: str = Field(description="Target URL to scan")
    test_types: List[str] = Field(
        default_factory=lambda: ["xss", "sql_injection", "injection", "access_control"],
        description="Types of tests to run"
    )
    include_report: bool = Field(
        default=True,
        description="Include a comprehensive report in the output"
    )

class DynamicSecurityScanTool(BaseTool):
    """Dynamic security scan tool for LangChain."""
    
    name: str = "dynamic_security_scanner"
    description: str = """
    Dynamic security scanner that constructs tests from OWASP and CWE databases.
    Can test for XSS, SQL injection, access control issues, and other vulnerabilities.
    """
    args_schema: Type[BaseModel] = DynamicSecurityScanInput
    security_tester: DynamicSecurityTester = Field(default_factory=DynamicSecurityTester)
    
    def _run(self, target_url: str, test_types: List[str], include_report: bool = True) -> str:
        """Run dynamic security scan."""
        try:
            # Create event loop for async operations
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Run the tests
            results = loop.run_until_complete(
                self.security_tester.run_all_tests(target_url, test_types)
            )
            
            # Generate output
            if include_report:
                output = self.security_tester.generate_report(results)
            else:
                # Just return a summary
                vulnerable = len([r for r in results if r.result != "not_vulnerable"])
                output = f"Security scan completed. {vulnerable} vulnerabilities found out of {len(results)} tests."
            
            return output
            
        except Exception as e:
            return f"Security scan failed: {str(e)}"
        finally:
            loop.run_until_complete(self.security_tester.close_session())
            loop.close()
    
    async def _arun(self, *args, **kwargs):
        """Async version of the tool."""
        raise NotImplementedError("Async operation not supported")

# Example usage
if __name__ == "__main__":
    # Create and run dynamic security scan
    security_tool = DynamicSecurityScanTool()
    
    # Run a comprehensive security scan
    result = security_tool._run(
        target_url="https://maxhodl.com",
        test_types=["xss", "sql_injection", "injection", "access_control"],
        include_report=True
    )
    
    print(result)