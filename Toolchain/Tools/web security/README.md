# Web Security Analysis Toolkit

## Overview

The **Web Security** toolkit provides comprehensive security analysis, vulnerability detection, and penetration testing capabilities for Vera. It combines automated scanning, AI-powered analysis, and dynamic testing to identify security issues in web applications and infrastructure.

## Purpose

The Security toolkit enables Vera to:
- **Detect vulnerabilities** in web applications
- **Perform penetration testing** autonomously
- **Analyze security headers** and configurations
- **Test authentication** and authorization
- **Monitor for security issues** proactively
- **Generate security reports** with remediation

## Components

### 1. Web Security Scanner (`web_security.py`)
Automated vulnerability scanning and detection.

### 2. Dynamic Security Tester (`dynamic_web_security.py`)
Active testing with payload injection and fuzzing.

### 3. AI-Powered MITM (`ai_in_the_middle.py`)
Intelligent traffic analysis and attack simulation.

## Architecture

```
Target Application
       ↓
Security Analysis Engine
       ├─→ Passive Scanning
       ├─→ Active Testing
       ├─→ AI Analysis
       └─→ Exploit Verification
              ↓
    Vulnerability Detection
              ↓
    Risk Assessment
              ↓
    Report Generation
              ↓
Knowledge Graph Storage
```

## Web Security Scanner

### Overview
Comprehensive automated security scanner for web applications.

### Features
- **OWASP Top 10 coverage**
- **Port scanning** and service detection
- **SSL/TLS analysis**
- **Header security** checks
- **Cookie security** analysis
- **Directory enumeration**
- **Subdomain discovery**
- **Technology fingerprinting**

### Usage

#### Basic Security Scan
```python
from Toolchain.Tools.web_security.web_security import WebSecurityScanner

scanner = WebSecurityScanner()

# Comprehensive scan
result = scanner.scan("https://example.com")

print(f"Vulnerabilities found: {len(result['vulnerabilities'])}")
print(f"Security score: {result['security_score']}/100")
print(f"Risk level: {result['risk_level']}")
```

#### Targeted Scans
```python
# Scan specific aspects
scanner = WebSecurityScanner()

# Headers only
headers_result = scanner.scan_headers("https://example.com")

# SSL/TLS only
ssl_result = scanner.scan_ssl("https://example.com")

# Authentication only
auth_result = scanner.scan_auth("https://example.com/login")
```

#### Advanced Configuration
```python
scanner = WebSecurityScanner(
    aggressive=True,  # More thorough testing
    timeout=60,
    verify_ssl=False,  # Test sites with self-signed certs
    user_agent="Vera Security Scanner/1.0",
    auth={
        "type": "basic",
        "username": "test",
        "password": "test"
    },
    scope={
        "include": ["https://example.com/*"],
        "exclude": ["https://example.com/admin/*"]
    }
)

result = scanner.scan("https://example.com")
```

### Vulnerability Categories

#### 1. Injection Flaws
**SQL Injection:**
```python
# Automatically tests for SQL injection
result = scanner.scan("https://example.com/search?q=test")

# Findings:
# - SQLi in search parameter (HIGH risk)
# - Payload: ' OR '1'='1
# - Response indicates database error
# - Recommendation: Use parameterized queries
```

**Command Injection:**
```python
# Tests for OS command injection
# - Tests common injection points
# - Verifies with time-based techniques
# - Identifies vulnerable parameters
```

**LDAP/XML/Template Injection:**
```python
# Comprehensive injection testing
vulnerabilities = result['vulnerabilities']
for vuln in vulnerabilities:
    if vuln['type'] == 'injection':
        print(f"Found {vuln['subtype']}: {vuln['location']}")
        print(f"Payload: {vuln['payload']}")
        print(f"Evidence: {vuln['evidence']}")
```

#### 2. Broken Authentication
```python
# Authentication testing
result = scanner.scan_auth("https://example.com/login")

# Checks:
# - Weak password policy
# - Session fixation
# - Credential stuffing
# - Brute force protection
# - Multi-factor authentication
# - Session timeout

for finding in result['findings']:
    print(f"Issue: {finding['title']}")
    print(f"Severity: {finding['severity']}")
    print(f"Fix: {finding['remediation']}")
```

#### 3. Sensitive Data Exposure
```python
# Data exposure checks
result = scanner.scan("https://example.com")

# Identifies:
# - Unencrypted data transmission
# - Weak SSL/TLS configuration
# - Sensitive data in URLs
# - Exposed API keys
# - Directory listings
# - Backup files exposed
```

#### 4. XML External Entities (XXE)
```python
# XXE vulnerability testing
xxe_result = scanner.test_xxe("https://example.com/upload")

if xxe_result['vulnerable']:
    print(f"XXE found at: {xxe_result['endpoint']}")
    print(f"Payload: {xxe_result['payload']}")
```

#### 5. Broken Access Control
```python
# Access control testing
result = scanner.scan_access_control("https://example.com")

# Tests:
# - Insecure direct object references
# - Missing function-level access control
# - CORS misconfiguration
# - Path traversal
```

#### 6. Security Misconfiguration
```python
# Configuration auditing
result = scanner.scan_config("https://example.com")

# Checks:
# - Default credentials
# - Unnecessary services enabled
# - Verbose error messages
# - Missing security patches
# - Unsafe file permissions
```

#### 7. Cross-Site Scripting (XSS)
```python
# XSS detection
xss_result = scanner.scan_xss("https://example.com")

# Finds:
# - Reflected XSS
# - Stored XSS
# - DOM-based XSS

for xss in xss_result['findings']:
    print(f"Type: {xss['xss_type']}")
    print(f"Parameter: {xss['parameter']}")
    print(f"Payload: {xss['payload']}")
    print(f"Context: {xss['context']}")  # HTML, JavaScript, attribute
```

#### 8. Insecure Deserialization
```python
# Deserialization vulnerability testing
result = scanner.scan("https://example.com")

if 'deserialization' in result['vulnerabilities']:
    print("Insecure deserialization detected!")
```

#### 9. Using Components with Known Vulnerabilities
```python
# Dependency scanning
result = scanner.scan("https://example.com")

# Cross-references with CVE database
for component in result['components']:
    print(f"Technology: {component['name']} {component['version']}")
    if component['vulnerabilities']:
        for cve in component['vulnerabilities']:
            print(f"  - {cve['id']}: {cve['description']}")
            print(f"    Severity: {cve['severity']}")
            print(f"    Fix: {cve['fix_version']}")
```

#### 10. Insufficient Logging & Monitoring
```python
# Logging assessment
result = scanner.assess_logging("https://example.com")

# Evaluates:
# - Event logging coverage
# - Log integrity
# - Monitoring capabilities
# - Alerting mechanisms
```

### Security Headers Analysis

```python
# Comprehensive header analysis
headers = scanner.scan_headers("https://example.com")

# Checks for:
print("Security Headers:")
print(f"  Content-Security-Policy: {headers['csp']}")
print(f"  X-Frame-Options: {headers['xfo']}")
print(f"  X-Content-Type-Options: {headers['xcto']}")
print(f"  Strict-Transport-Security: {headers['hsts']}")
print(f"  X-XSS-Protection: {headers['xxp']}")
print(f"  Referrer-Policy: {headers['rp']}")
print(f"  Permissions-Policy: {headers['pp']}")

# Recommendations
for header, status in headers.items():
    if status == 'missing':
        print(f"⚠ Missing: {header}")
        print(f"  Add: {headers[header + '_example']}")
```

### SSL/TLS Analysis

```python
# SSL/TLS security assessment
ssl = scanner.scan_ssl("https://example.com")

print(f"SSL Grade: {ssl['grade']}")  # A+, A, B, C, D, F
print(f"Protocol: {ssl['protocol']}")  # TLS 1.3
print(f"Cipher: {ssl['cipher']}")
print(f"Key Exchange: {ssl['key_exchange']}")
print(f"Certificate Validity: {ssl['cert_valid']}")

# Issues
for issue in ssl['issues']:
    print(f"⚠ {issue['severity']}: {issue['description']}")
    print(f"  Fix: {issue['remediation']}")

# Certificate details
cert = ssl['certificate']
print(f"Issuer: {cert['issuer']}")
print(f"Expires: {cert['expiry']}")
print(f"Subject: {cert['subject']}")
```

## Dynamic Security Tester

### Overview
Active security testing with payload injection, fuzzing, and attack simulation.

### Features
- **Payload generation** and injection
- **Fuzzing** input fields
- **Attack chain** construction
- **Exploit verification**
- **Bypass testing** (WAF, rate limits)

### Usage

#### Basic Dynamic Testing
```python
from Toolchain.Tools.web_security.dynamic_web_security import DynamicSecurityTester

tester = DynamicSecurityTester()

# Test all injection vectors
result = tester.test("https://example.com/search?q=test")

# Results include:
# - Successful exploits
# - Partial findings
# - False positives filtered
```

#### Fuzzing
```python
# Fuzz input parameters
result = tester.fuzz(
    url="https://example.com/api/user",
    method="POST",
    data={"username": "FUZZ", "email": "FUZZ"},
    payloads=[
        "admin' OR '1'='1",
        "../../../etc/passwd",
        "<script>alert(1)</script>",
        "${7*7}",  # Template injection
        "{{7*7}}"  # SSTI
    ]
)

for finding in result['findings']:
    print(f"Payload: {finding['payload']}")
    print(f"Response: {finding['response_diff']}")
    print(f"Vulnerable: {finding['is_vulnerable']}")
```

#### Custom Attack Chains
```python
# Multi-step attack simulation
chain = [
    {"action": "enumerate_users", "endpoint": "/api/users"},
    {"action": "test_auth", "endpoint": "/login"},
    {"action": "exploit_sqli", "parameter": "username"},
    {"action": "escalate_privileges", "payload": "admin"},
    {"action": "extract_data", "table": "users"}
]

result = tester.execute_chain("https://example.com", chain)

if result['success']:
    print(f"Attack successful!")
    print(f"Data extracted: {result['data']}")
```

#### WAF Bypass Testing
```python
# Test WAF evasion techniques
result = tester.bypass_waf(
    url="https://example.com/search",
    payload="' OR 1=1--",
    techniques=[
        "case_variation",
        "encoding",
        "concatenation",
        "comment_injection",
        "whitespace_manipulation"
    ]
)

if result['bypassed']:
    print(f"WAF bypassed with: {result['successful_technique']}")
    print(f"Final payload: {result['final_payload']}")
```

## AI-Powered MITM

### Overview
Intelligent man-in-the-middle analysis using AI to detect anomalies, attacks, and vulnerabilities in real-time traffic.

### Features
- **Traffic interception** and analysis
- **AI-based anomaly detection**
- **Attack pattern recognition**
- **Payload generation** using LLM
- **Automated exploitation**

### Usage

#### Traffic Analysis
```python
from Toolchain.Tools.web_security.ai_in_the_middle import AIPoweredMITM

mitm = AIPoweredMITM()

# Start intercepting traffic
mitm.start_proxy(port=8080)

# Analyze captured traffic with AI
analysis = mitm.analyze_traffic()

print(f"Requests analyzed: {analysis['request_count']}")
print(f"Anomalies detected: {len(analysis['anomalies'])}")
print(f"Potential exploits: {len(analysis['exploits'])}")
```

#### AI-Generated Exploits
```python
# Use LLM to generate targeted exploits
target = {
    "url": "https://example.com/api/data",
    "method": "POST",
    "headers": {"Content-Type": "application/json"},
    "body": {"id": "123"}
}

# AI analyzes and generates exploits
exploits = mitm.generate_exploits(target)

for exploit in exploits:
    print(f"Vulnerability: {exploit['type']}")
    print(f"Payload: {exploit['payload']}")
    print(f"Expected outcome: {exploit['expected']}")
    print(f"Confidence: {exploit['confidence']}")

    # Test exploit
    result = mitm.test_exploit(exploit)
    if result['successful']:
        print(f"✓ Exploit successful!")
```

#### Automated Attack Simulation
```python
# AI-driven attack simulation
result = mitm.simulate_attack(
    target="https://example.com",
    attack_types=["injection", "xss", "csrf", "auth_bypass"],
    learning_mode=True  # Learn from results
)

for attack in result['attacks']:
    print(f"Attack: {attack['type']}")
    print(f"Success rate: {attack['success_rate']}")
    print(f"Payloads tested: {attack['payloads_tested']}")
    print(f"Vulnerabilities found: {len(attack['findings'])}")
```

## Security Report Generation

### Comprehensive Reports
```python
# Generate detailed security report
scanner = WebSecurityScanner()
result = scanner.scan("https://example.com")

report = scanner.generate_report(result, format="pdf")

# Report includes:
# - Executive summary
# - Vulnerability details
# - Risk ratings (CVSS scores)
# - Remediation steps
# - Code examples
# - Compliance mapping (OWASP, PCI-DSS, etc.)
```

### Integration with Memory
```python
# Store findings in knowledge graph
from Memory.memory import VeraMemory

memory = VeraMemory()

# Create security assessment entity
memory.create_entity(
    entity_type="SecurityAssessment",
    properties={
        "target": "example.com",
        "date": "2025-01-16",
        "vulnerabilities": result['vulnerabilities'],
        "risk_level": result['risk_level'],
        "score": result['security_score']
    },
    tags=["security", "assessment", "vulnerability"]
)

# Link to target website
memory.create_relationship(
    source="SecurityAssessment:example_com_2025",
    target="Website:example.com",
    relationship_type="ASSESSES"
)
```

## Use Cases

### 1. Pre-Deployment Security Check
```python
# Scan before deployment
scanner = WebSecurityScanner()
result = scanner.scan("https://staging.example.com")

if result['security_score'] < 80:
    print("⚠ Security issues found! Deployment blocked.")
    print("Fix these critical issues:")
    for vuln in result['vulnerabilities']:
        if vuln['severity'] == 'critical':
            print(f"  - {vuln['title']}: {vuln['remediation']}")
else:
    print("✓ Security check passed. Ready for deployment.")
```

### 2. Continuous Monitoring
```python
# Daily security scans
from BackgroundCognition.proactive_background_focus import PBC

pbc = PBC()

pbc.schedule_task(
    task="security_scan",
    target="https://example.com",
    frequency="daily",
    alert_on=["new_vulnerabilities", "score_decrease"]
)

# PBC runs scan daily and alerts on changes
```

### 3. Bug Bounty Automation
```python
# Automated bug bounty hunting
scanner = WebSecurityScanner(aggressive=True)
tester = DynamicSecurityTester()

targets = [
    "https://target1.com",
    "https://target2.com",
    "https://target3.com"
]

for target in targets:
    scan_result = scanner.scan(target)
    test_result = tester.test(target)

    # Filter high-value bugs
    critical_bugs = [
        vuln for vuln in scan_result['vulnerabilities']
        if vuln['severity'] in ['critical', 'high']
        and vuln['exploitable']
    ]

    for bug in critical_bugs:
        print(f"Potential bug bounty: {bug['title']}")
        print(f"Target: {target}")
        print(f"Severity: {bug['severity']}")
        print(f"Proof of concept: {bug['poc']}")
```

### 4. Compliance Auditing
```python
# PCI-DSS compliance check
result = scanner.scan("https://payment.example.com")

compliance = scanner.check_compliance(result, standard="PCI-DSS")

print(f"PCI-DSS Compliance: {compliance['compliant']}")
print(f"Requirements met: {compliance['met']}/{compliance['total']}")

for requirement in compliance['failed']:
    print(f"⚠ Requirement {requirement['id']}: {requirement['description']}")
    print(f"  Fix: {requirement['remediation']}")
```

## Best Practices

### 1. Get Authorization
**Always obtain written permission** before scanning systems you don't own.

### 2. Start Non-Invasive
```python
# Begin with passive scanning
scanner = WebSecurityScanner(aggressive=False)
```

### 3. Use Scoping
```python
# Limit scan scope
scanner = WebSecurityScanner(
    scope={
        "include": ["https://example.com/app/*"],
        "exclude": [
            "https://example.com/admin/*",
            "https://example.com/logout"
        ]
    }
)
```

### 4. Rate Limit
```python
# Avoid overwhelming target
scanner = WebSecurityScanner(
    rate_limit=10,  # 10 requests per second
    delay=1.0  # 1 second between scans
)
```

### 5. Verify Findings
```python
# Manually verify critical findings
for vuln in result['vulnerabilities']:
    if vuln['severity'] == 'critical':
        verified = scanner.verify_vulnerability(vuln)
        if not verified:
            print(f"False positive: {vuln['title']}")
```

## Configuration

### Environment Variables
```bash
# Scanner settings
SECURITY_SCANNER_AGGRESSIVE=false
SECURITY_SCANNER_TIMEOUT=60
SECURITY_SCANNER_USER_AGENT="Vera Security Scanner/1.0"

# Payload settings
SECURITY_PAYLOAD_DB=/path/to/payloads.db
SECURITY_CUSTOM_PAYLOADS=/path/to/custom_payloads.txt

# Reporting
SECURITY_REPORT_FORMAT=pdf
SECURITY_REPORT_PATH=./security_reports/
```

## Troubleshooting

### False Positives
```python
# Verify findings
scanner = WebSecurityScanner(verify_findings=True)
```

### Rate Limiting/Blocking
```python
# Reduce aggressiveness
scanner = WebSecurityScanner(
    aggressive=False,
    rate_limit=5,
    delay=2.0
)
```

### SSL Errors
```python
# Handle self-signed certificates
scanner = WebSecurityScanner(verify_ssl=False)
```

## Related Documentation

- [Crawlers](../crawlers/) - Web scraping for reconnaissance
- [Toolchain Engine](../../README.md) - Tool orchestration
- [Memory System](../../../Memory/) - Finding storage

## Legal & Ethical Guidelines

**WARNING:** These tools can cause harm if misused.

### Authorized Use Only
- Bug bounty programs
- Penetration testing contracts
- Your own systems
- Educational environments
- Security research (with permission)

### Prohibited Use
- Unauthorized system access
- Denial of service attacks
- Data theft or destruction
- Privacy violations
- Any illegal activity

**By using these tools, you agree to use them responsibly and legally.**

---

**Related Components:**
- [Toolchain](../../) - Security testing orchestration
- [Memory](../../../Memory/) - Vulnerability tracking
- [Background Cognition](../../../BackgroundCognition/) - Continuous monitoring
