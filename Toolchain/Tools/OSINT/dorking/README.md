# Enhanced Search Engine Dorking Toolkit

A comprehensive, modular dorking toolkit with intelligent keyword-to-dork conversion, multi-engine support, and graph memory integration.

## 🎯 Features

### ✨ New Features (v2.0)
- **Intelligent Keyword Search**: Just type keywords like "webcam" or "admin login" - the system generates appropriate dorks
- **Auto-Detection**: Automatically detects whether input is a keyword or custom dork
- **Smart Query Generation**: Converts simple keywords into multiple optimized search queries
- **Hybrid Mode**: Combine keywords with filters (file types, sites, date ranges)

### 🛠️ Core Features
- **Multi-Engine Support**: Google, Bing, DuckDuckGo with more coming
- **Anti-Detection Measures**: User agent rotation, session management, random delays, referrer headers
- **500+ Pre-Built Dork Patterns**: Organized by category
- **Category-Based Searches**: Files, logins, cameras, devices, misconfigurations, etc.
- **Information Extraction**: Automatically extracts emails, phone numbers, IPs
- **Graph Memory Integration**: Stores discoveries in Neo4j for relationship mapping
- **Result Deduplication**: Prevents duplicate results across queries

## 📁 Package Structure

```
dorking/
├── __init__.py           # Main entry point & exports
├── config.py            # Configuration classes and enums
├── schemas.py           # Pydantic input models
├── dork_patterns.py     # 500+ dork pattern database
├── dork_generator.py    # Keyword-to-dork intelligence
├── search_engines.py    # Search engine implementations
├── mapper.py            # Main DorkingMapper orchestrator
└── tools.py             # LangChain tool integration
```

## 🚀 Quick Start

### Installation

```bash
# Required dependencies
pip install requests beautifulsoup4 pydantic langchain-core

# Optional (for better anti-detection)
pip install fake-useragent
```

### Basic Usage

```python
from dorking import add_dorking_tools, DorkingConfig, DorkingMapper

# 1. Add tools to your agent
tools = []
add_dorking_tools(tools, agent)

# 2. Or use directly
config = DorkingConfig.stealth_mode()
mapper = DorkingMapper(agent, config)

# Simple keyword search
for result in mapper.unified_search("webcam"):
    print(result)

# Keyword with target
for result in mapper.unified_search("admin login", target="example.com"):
    print(result)

# Keyword with filters
for result in mapper.unified_search(
    search="config",
    file_type="env",
    site="github.com"
):
    print(result)

# Custom dork query
for result in mapper.unified_search('intitle:"webcam" inurl:view'):
    print(result)
```

## 📚 Available Tools

### New Unified Tools

#### 1. `dork_search` - Intelligent Dorking
The main tool supporting both keywords and custom dorks with auto-detection.

```python
# Simple keywords
dork_search(search="webcam")
dork_search(search="admin login")
dork_search(search="database")

# With filters
dork_search(search="config", file_type="env")
dork_search(search="camera", target="example.com")

# Custom dorks
dork_search(search='intitle:"webcam" inurl:view.shtml')
dork_search(search='filetype:sql "password"')
```

**Parameters:**
- `search`: Keywords or custom dork query
- `target`: Optional target domain/keyword
- `file_type`: Filter by file extension (sql, pdf, env, etc.)
- `site`: Restrict to specific domain
- `exclude_sites`: Domains to exclude
- `date_range`: Time filter (day, week, month, year)
- `max_results`: Maximum results per engine (default: 50)
- `engines`: List of engines to use
- `mode`: 'smart' (auto), 'keyword', or 'custom'

#### 2. `dork_quick` - Quick Keyword Search
Fast search with minimal configuration, returns top 30 results.

```python
dork_quick(keywords="webcam")
dork_quick(keywords="admin panel", target="example.com")
```

### Original Category-Specific Tools

#### 3. `dork_search_files` - Exposed Files
Search for SQL dumps, configs, logs, backups, credentials.

```python
dork_search_files(
    target="example.com",
    file_types=["sql", "env", "config"],
    keywords=["password", "admin"]
)
```

#### 4. `dork_search_logins` - Login Portals
Find admin panels, webmail, phpMyAdmin, CMS logins.

```python
dork_search_logins(
    target="example.com",
    login_types=["admin", "webmail", "phpmyadmin"]
)
```

#### 5. `dork_search_devices` - Network Devices
Discover webcams, printers, routers, NAS, IoT, SCADA.

```python
dork_search_devices(
    target="example.com",
    device_types=["camera", "printer", "router"]
)
```

#### 6. `dork_search_misconfigs` - Misconfigurations
Find directory listings, error pages, exposed .git/.svn.

```python
dork_search_misconfigs(
    target="example.com",
    misconfig_types=["directory_listing", "error_page", "git"]
)
```

#### 7. `dork_search_people` - OSINT
Search for emails, phones, social profiles, resumes.

```python
dork_search_people(
    target="John Doe",
    info_types=["email", "phone", "linkedin"]
)
```

#### 8. `dork_custom` - Custom Dork Execution
Execute specific dork query on chosen engine.

```python
dork_custom(
    target="example.com",
    dork_query='intitle:"admin" inurl:login',
    engine="google"
)
```

#### 9. `dork_comprehensive` - Multi-Category Scan
Comprehensive scan across multiple categories.

```python
dork_comprehensive(
    target="example.com",
    categories=["files", "logins", "misconfigs"],
    depth="standard"  # quick, standard, or deep
)
```

## ⚙️ Configuration

### Configuration Modes

```python
from dorking import DorkingConfig

# Stealth mode - Maximum anti-detection
config = DorkingConfig.stealth_mode()

# Aggressive mode - Fast but higher detection risk
config = DorkingConfig.aggressive_mode()

# Balanced mode - Default
config = DorkingConfig.balanced_mode()

# Custom configuration
config = DorkingConfig(
    engines=["google", "bing"],
    min_delay=5.0,
    max_delay=10.0,
    max_results_per_engine=100,
    extract_emails=True,
    check_availability=True
)
```

### Configuration Options

```python
@dataclass
class DorkingConfig:
    # Search engines
    engines: List[str] = ["google", "bing", "duckduckgo"]
    
    # Anti-detection
    use_random_user_agents: bool = True
    min_delay: float = 3.0
    max_delay: float = 8.0
    rotate_sessions: bool = True
    session_rotation_interval: int = 10
    
    # Search parameters
    max_results_per_engine: int = 50
    max_pages_per_search: int = 5
    
    # Result processing
    extract_emails: bool = True
    extract_phones: bool = True
    extract_ips: bool = True
    check_availability: bool = True
    
    # Filtering
    domain_filter: Optional[str] = None
    exclude_domains: Optional[List[str]] = None
    date_filter: Optional[str] = None  # day, week, month, year
    file_type_filter: Optional[str] = None
```

## 🎯 Keyword Patterns

The system recognizes these keywords and generates appropriate dorks:

### Network Devices
- `webcam`, `camera`, `printer`, `router`

### Login Portals
- `admin`, `login`, `dashboard`, `phpmyadmin`

### Files & Documents
- `database`, `backup`, `config`, `password`, `credentials`, `log`

### Misconfigurations
- `directory listing`, `error`, `exposed`

### Cloud Storage
- `s3`, `aws`, `azure`

### Development
- `api`, `git`, `jenkins`

### Information Types
- `email`, `phone`, `resume`

And many more! See `dork_generator.py` for the complete list.

## 🔍 Search Categories

### Files
- SQL dumps (`.sql`, database exports)
- Config files (`.env`, `.ini`, `.yaml`)
- Logs (`.log`, error logs, access logs)
- Backups (`.bak`, `.zip`, `.tar.gz`)
- Credentials (password files, key files)

### Logins
- Admin panels
- Webmail interfaces
- Database management (phpMyAdmin, Adminer)
- CMS logins (WordPress, Joomla, Drupal)
- Control panels (cPanel, Plesk)

### Devices
- Webcams and IP cameras
- Network printers
- Routers and firewalls
- NAS devices
- IoT devices
- SCADA/ICS systems

### Misconfigurations
- Directory listings
- Error pages (PHP errors, SQL errors)
- Debug pages (phpinfo, test pages)
- Exposed version control (.git, .svn)

### Documents
- PDFs, spreadsheets, presentations
- Confidential documents
- Financial records
- Personal information
- Legal documents

### Cloud Storage
- AWS S3 buckets
- Azure Blob storage
- Google Cloud Storage
- Dropbox shares

### Code Repositories
- GitHub, GitLab, Bitbucket
- Pastebin dumps
- Exposed API keys and secrets

## 🧠 Memory Integration

Results are automatically stored in Neo4j graph memory:

```
Session -> DorkSearch -> WebResource
                      -> WebResource
                      -> WebResource
```

Each `WebResource` node includes:
- URL and title
- Search snippet
- Discovery timestamp
- Extracted emails, phones, IPs
- Availability status

## 🛡️ Anti-Detection Features

1. **User Agent Rotation**: Random user agents (with fake-useragent support)
2. **Session Management**: Automatic session rotation
3. **Random Delays**: Configurable delays between requests
4. **Referrer Headers**: Realistic referrer rotation
5. **Captcha Detection**: Automatic captcha detection and graceful degradation
6. **Result Deduplication**: Prevents re-fetching same URLs

## 📊 Usage Examples

### Example 1: Simple Keyword Search
```python
# Just search with keywords
for result in mapper.unified_search("exposed camera"):
    print(result)
```

### Example 2: Targeted Search
```python
# Search specific domain
for result in mapper.unified_search(
    search="admin login",
    target="company.com"
):
    print(result)
```

### Example 3: File Type Search
```python
# Find specific file types
for result in mapper.unified_search(
    search="configuration",
    file_type="env",
    exclude_sites=["github.com"]
):
    print(result)
```

### Example 4: Custom Dork
```python
# Use advanced dork syntax
for result in mapper.unified_search(
    search='site:s3.amazonaws.com filetype:pdf "confidential"'
):
    print(result)
```

### Example 5: Multi-Engine Search
```python
# Search across multiple engines
for result in mapper.unified_search(
    search="webcam",
    engines=["google", "bing", "duckduckgo"],
    max_results=100
):
    print(result)
```

## 🔧 Direct Component Usage

### Using DorkGenerator
```python
from dorking import DorkGenerator

# Generate dorks from keywords
dorks = DorkGenerator.generate_dorks_from_keywords(
    "admin login",
    target="example.com",
    file_type="php"
)

# Check if query is a custom dork
is_custom = DorkGenerator.is_custom_dork('intitle:"login"')

# Enhance query with filters
enhanced = DorkGenerator.parse_and_enhance_query(
    "admin",
    site="example.com",
    file_type="php"
)
```

### Using DorkPatterns
```python
from dorking import DorkPatterns

# Get dorks by category
file_dorks = DorkPatterns.get_dorks_by_category("files")
login_dorks = DorkPatterns.get_dorks_by_category("logins")

# Count patterns
counts = DorkPatterns.count_patterns()
print(f"Total file dorks: {counts['files']}")
```

### Using Search Engines Directly
```python
from dorking import GoogleSearchEngine, DorkingConfig

config = DorkingConfig()
engine = GoogleSearchEngine(config)

results = engine.search('intitle:"webcam"', max_results=50)
for result in results:
    print(f"{result['title']}: {result['url']}")
```

## 📝 Dependencies

### Required
- `requests` - HTTP client
- `beautifulsoup4` - HTML parsing
- `pydantic` - Data validation
- `langchain-core` - Tool integration

### Optional
- `fake-useragent` - Better user agent rotation (highly recommended)

## ⚠️ Disclaimer

This toolkit is for authorized security research and penetration testing only. Always ensure you have proper authorization before scanning or accessing any systems. Unauthorized access to computer systems is illegal.

## 📄 License

See LICENSE file for details.

## 🤝 Contributing

Contributions welcome! Please ensure all features are preserved when refactoring.

## 📮 Support

For issues or questions, please open an issue on the project repository.