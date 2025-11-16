# Web Crawlers & Corpus Analysis

## Overview

The **Crawlers** toolkit provides sophisticated web scraping and corpus analysis capabilities for Vera. It enables systematic website exploration, content extraction, technology detection, and knowledge graph integration.

## Purpose

Crawlers enable Vera to:
- **Map entire websites** into the knowledge graph
- **Extract structured data** from unstructured web pages
- **Detect technologies** used by websites
- **Build corpus representations** for analysis
- **Monitor web resources** for changes
- **Scrape data** for research and analysis

## Components

### 1. Corpus Crawler (`corpus_crawler.py`)
Comprehensive website mapping and content extraction.

### 2. Total Crawl (`total_crawl.py`)
Deep web crawling with recursive link following.

### 3. Technology Detection (`tech_detection_rules.json`)
Rules for identifying web technologies and frameworks.

## Architecture

```
URL Input
   ↓
Crawler Selection (Corpus/Total)
   ↓
Page Fetching (requests/selenium)
   ↓
Content Parsing (BeautifulSoup/lxml)
   ↓
Technology Detection
   ↓
Data Extraction
   ↓
Knowledge Graph Integration
   ↓
Storage (Memory Layer 3)
```

## Corpus Crawler

### Overview
Maps websites into structured representations, creating a graph of pages, links, and resources.

### Features
- **Sitemap parsing** - Automatic sitemap.xml discovery
- **Recursive crawling** - Follow links with depth limits
- **Content extraction** - Text, images, links, metadata
- **Technology detection** - Identify frameworks, CMSs, analytics
- **Resource mapping** - JavaScript, CSS, images, fonts
- **Knowledge graph integration** - Store as connected entities

### Usage

#### Basic Crawl
```python
from Toolchain.Tools.crawlers.corpus_crawler import CorpusCrawler

crawler = CorpusCrawler()

# Crawl a website
result = crawler.crawl(
    url="https://example.com",
    max_depth=3,
    max_pages=100
)

print(f"Pages crawled: {result['pages_count']}")
print(f"Technologies: {result['technologies']}")
print(f"Graph nodes: {result['graph_nodes']}")
```

#### Advanced Configuration
```python
crawler = CorpusCrawler(
    max_depth=5,
    max_pages=500,
    respect_robots_txt=True,
    user_agent="Vera-AI Bot/1.0",
    delay=1.0,  # Seconds between requests
    timeout=30,
    verify_ssl=True,
    extract_images=True,
    extract_scripts=True,
    detect_technologies=True,
    store_in_memory=True
)

result = crawler.crawl("https://docs.example.com")
```

#### With Memory Integration
```python
# Automatically store in knowledge graph
crawler = CorpusCrawler(store_in_memory=True)

result = crawler.crawl("https://example.com")

# Graph structure created:
# (Website:example.com)
#   ├─→ (Page:/index.html)
#   │     ├─→ (Link:/about.html)
#   │     ├─→ (Image:/logo.png)
#   │     └─→ (Script:/app.js)
#   ├─→ (Page:/about.html)
#   └─→ (Technology:React)

# Query the graph
from Memory.memory import VeraMemory
memory = VeraMemory()

pages = memory.query_graph(
    "MATCH (w:Website {domain: 'example.com'})-[:CONTAINS]->(p:Page) RETURN p"
)
```

### Extraction Capabilities

#### Text Content
```python
# Extract and clean text
result = crawler.crawl("https://example.com")
for page in result['pages']:
    print(f"Title: {page['title']}")
    print(f"Headings: {page['headings']}")
    print(f"Content: {page['clean_text'][:200]}...")
```

#### Structured Data
```python
# Extract metadata
for page in result['pages']:
    print(f"Meta description: {page['meta']['description']}")
    print(f"Open Graph: {page['meta']['og']}")
    print(f"JSON-LD: {page['structured_data']}")
```

#### Links and Resources
```python
# Analyze link structure
for page in result['pages']:
    print(f"Internal links: {len(page['internal_links'])}")
    print(f"External links: {len(page['external_links'])}")
    print(f"Images: {len(page['images'])}")
    print(f"Scripts: {len(page['scripts'])}")
```

### Technology Detection

#### Detected Technologies
- **Frameworks:** React, Vue, Angular, Django, Rails
- **CMS:** WordPress, Drupal, Joomla
- **Analytics:** Google Analytics, Matomo
- **Web Servers:** Nginx, Apache, IIS
- **CDN:** Cloudflare, Akamai
- **JavaScript Libraries:** jQuery, Lodash, D3.js

#### Detection Methods
```python
# Technology detection
result = crawler.crawl("https://example.com")

for tech in result['technologies']:
    print(f"Technology: {tech['name']}")
    print(f"Version: {tech.get('version', 'unknown')}")
    print(f"Confidence: {tech['confidence']}")
    print(f"Detection method: {tech['method']}")  # header, script, meta, etc.
```

#### Custom Detection Rules
**Edit `tech_detection_rules.json`:**
```json
{
  "custom_framework": {
    "name": "CustomFramework",
    "detection": {
      "script": {
        "pattern": "customframework\\.min\\.js",
        "confidence": 0.9
      },
      "html": {
        "pattern": "data-custom-version=\"([0-9\\.]+)\"",
        "version_group": 1,
        "confidence": 0.95
      }
    }
  }
}
```

### Sitemap Integration

```python
# Auto-detect and parse sitemap.xml
crawler = CorpusCrawler(use_sitemap=True)

result = crawler.crawl("https://example.com")

# Prioritizes URLs from sitemap
# Respects priority and change frequency
# Falls back to crawling if sitemap unavailable
```

## Total Crawl

### Overview
Deep, recursive web crawling for comprehensive data extraction.

### Features
- **Unlimited depth** - Crawl entire site hierarchies
- **JavaScript rendering** - Uses Selenium for dynamic content
- **Screenshot capture** - Save page screenshots
- **Form interaction** - Submit forms, click buttons
- **Authentication** - Handle login-protected areas
- **Proxy support** - Route through proxies

### Usage

#### Basic Total Crawl
```python
from Toolchain.Tools.crawlers.total_crawl import TotalCrawl

crawler = TotalCrawl()

result = crawler.crawl(
    start_url="https://example.com",
    max_pages=1000,
    render_js=False  # Fast crawling without JS
)
```

#### With JavaScript Rendering
```python
# Crawl SPAs and dynamic sites
crawler = TotalCrawl(render_js=True)

result = crawler.crawl(
    start_url="https://react-app.example.com",
    wait_for_selector=".content-loaded",  # Wait for dynamic content
    screenshot=True  # Capture screenshots
)

# Screenshots saved to: ./screenshots/example.com/
```

#### With Authentication
```python
# Crawl login-protected content
crawler = TotalCrawl(render_js=True)

result = crawler.crawl(
    start_url="https://app.example.com",
    auth={
        "type": "form",
        "login_url": "https://app.example.com/login",
        "username_field": "email",
        "password_field": "password",
        "username": "user@example.com",
        "password": "secret",
        "submit_button": "button[type='submit']"
    }
)
```

#### With Proxies
```python
# Route through proxy
crawler = TotalCrawl(
    proxy="http://proxy.example.com:8080",
    proxy_auth=("user", "pass")
)

result = crawler.crawl("https://example.com")
```

### Advanced Features

#### Custom Extraction Rules
```python
# Define custom extraction
crawler = TotalCrawl()

result = crawler.crawl(
    start_url="https://shop.example.com",
    extraction_rules={
        "product_title": {"selector": "h1.product-name", "attr": "text"},
        "product_price": {"selector": ".price", "attr": "text"},
        "product_image": {"selector": "img.product-img", "attr": "src"},
        "product_description": {"selector": ".description", "attr": "text"}
    }
)

for page in result['pages']:
    if 'product_title' in page['extracted']:
        print(f"Product: {page['extracted']['product_title']}")
        print(f"Price: {page['extracted']['product_price']}")
```

#### Rate Limiting
```python
# Respectful crawling
crawler = TotalCrawl(
    delay=2.0,  # 2 seconds between requests
    concurrent_requests=3,  # Max 3 concurrent requests
    respect_robots_txt=True
)
```

#### Custom Headers
```python
# Custom user agent and headers
crawler = TotalCrawl(
    headers={
        "User-Agent": "Vera-AI Research Bot/1.0",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br"
    }
)
```

## Integration with Knowledge Graph

### Automatic Graph Creation

Crawlers automatically create rich graph structures:

```cypher
// Website node
CREATE (w:Website {
  domain: "example.com",
  crawled_at: "2025-01-16T10:00:00Z",
  page_count: 150,
  technologies: ["React", "Nginx", "Google Analytics"]
})

// Pages and links
CREATE (w)-[:CONTAINS]->(p1:Page {url: "/", title: "Home"})
CREATE (w)-[:CONTAINS]->(p2:Page {url: "/about", title: "About"})
CREATE (p1)-[:LINKS_TO]->(p2)

// Resources
CREATE (p1)-[:USES]->(s:Script {src: "/app.js", size: 45000})
CREATE (p1)-[:USES]->(i:Image {src: "/logo.png", alt: "Logo"})

// Technologies
CREATE (w)-[:USES_TECHNOLOGY]->(t:Technology {name: "React", version: "18.0"})
```

### Querying Crawled Data

```cypher
// Find all pages linking to a specific page
MATCH (p1:Page)-[:LINKS_TO]->(p2:Page {url: "/pricing"})
RETURN p1.url, p1.title

// Find all websites using React
MATCH (w:Website)-[:USES_TECHNOLOGY]->(t:Technology {name: "React"})
RETURN w.domain, t.version

// Find broken links (404s)
MATCH (p:Page)-[:LINKS_TO]->(target:Page)
WHERE target.status_code = 404
RETURN p.url, target.url

// Analyze site structure depth
MATCH path = (w:Website)-[:CONTAINS]->(:Page)-[:LINKS_TO*]->(p:Page)
RETURN w.domain, length(path) as depth
ORDER BY depth DESC
```

## Use Cases

### 1. Documentation Mapping
```python
# Map API documentation
crawler = CorpusCrawler(store_in_memory=True)

result = crawler.crawl(
    url="https://api.example.com/docs",
    max_depth=10,
    extract_code_blocks=True
)

# Later retrieve relevant docs
memory.query("OAuth2 authentication examples", layers=[3])
```

### 2. Competitor Analysis
```python
# Analyze competitor websites
crawler = CorpusCrawler()

competitors = [
    "https://competitor1.com",
    "https://competitor2.com",
    "https://competitor3.com"
]

for url in competitors:
    result = crawler.crawl(url, max_depth=3)

    print(f"Competitor: {url}")
    print(f"Technologies: {result['technologies']}")
    print(f"Pages: {result['pages_count']}")
    print(f"Features detected: {result['features']}")
```

### 3. Content Monitoring
```python
# Monitor for changes
crawler = CorpusCrawler()

# Initial crawl
result1 = crawler.crawl("https://example.com/changelog")
initial_content = result1['pages'][0]['content']

# Later crawl
result2 = crawler.crawl("https://example.com/changelog")
new_content = result2['pages'][0]['content']

# Detect changes
if initial_content != new_content:
    changes = crawler.diff(initial_content, new_content)
    print(f"Changes detected: {changes}")
```

### 4. Data Extraction
```python
# Extract product catalog
crawler = TotalCrawl(render_js=True)

result = crawler.crawl(
    start_url="https://shop.example.com/products",
    extraction_rules={
        "name": {"selector": "h2.product-name"},
        "price": {"selector": ".price"},
        "rating": {"selector": ".rating", "attr": "data-rating"}
    },
    filter_pages=lambda url: "/product/" in url
)

products = [
    page['extracted']
    for page in result['pages']
    if page['extracted']
]

# Store in memory
memory.store_batch(products, entity_type="Product")
```

## Configuration

### Environment Variables
```bash
# Crawler settings
CRAWLER_USER_AGENT="Vera-AI Bot/1.0"
CRAWLER_DELAY=1.0
CRAWLER_MAX_DEPTH=5
CRAWLER_TIMEOUT=30

# Selenium settings (for Total Crawl)
SELENIUM_DRIVER=chrome
SELENIUM_HEADLESS=true
SELENIUM_WINDOW_SIZE=1920x1080

# Proxy settings
CRAWLER_PROXY_URL=http://proxy.example.com:8080
CRAWLER_PROXY_USERNAME=user
CRAWLER_PROXY_PASSWORD=pass
```

### Configuration File
**`crawler_config.json`:**
```json
{
  "corpus_crawler": {
    "max_depth": 5,
    "max_pages": 500,
    "delay": 1.0,
    "respect_robots_txt": true,
    "detect_technologies": true,
    "extract_images": true,
    "store_in_memory": true
  },
  "total_crawl": {
    "render_js": false,
    "screenshot": false,
    "max_pages": 1000,
    "concurrent_requests": 5,
    "timeout": 30
  }
}
```

## Best Practices

### 1. Respect robots.txt
```python
crawler = CorpusCrawler(respect_robots_txt=True)
```

### 2. Use Appropriate Delays
```python
# At least 1 second between requests
crawler = CorpusCrawler(delay=1.0)
```

### 3. Set Realistic Limits
```python
# Avoid crawling entire internet
crawler = CorpusCrawler(
    max_depth=5,  # Reasonable depth
    max_pages=1000  # Reasonable page limit
)
```

### 4. Handle Errors Gracefully
```python
result = crawler.crawl("https://example.com")

for page in result['pages']:
    if page['status_code'] >= 400:
        print(f"Error on {page['url']}: {page['status_code']}")
```

### 5. Identify Your Bot
```python
crawler = CorpusCrawler(
    user_agent="Vera-AI Bot/1.0 (+https://github.com/BoeJaker/Vera-AI)"
)
```

## Troubleshooting

### JavaScript Not Rendering
```bash
# Install Selenium drivers
playwright install chromium

# Or use browser-specific drivers
apt-get install chromium-chromedriver
```

### Rate Limiting/Blocking
```python
# Increase delay
crawler = CorpusCrawler(delay=3.0)

# Use proxy
crawler = CorpusCrawler(proxy="http://proxy.example.com:8080")

# Rotate user agents
crawler = CorpusCrawler(rotate_user_agents=True)
```

### Memory Issues with Large Crawls
```python
# Process in batches
crawler = CorpusCrawler(batch_size=100)

for batch in crawler.crawl_generator("https://example.com"):
    process_batch(batch)
    # Batch is garbage collected after processing
```

## Related Documentation

- [Toolchain Engine](../../README.md) - Tool orchestration
- [Memory System](../../../Memory/) - Knowledge graph storage
- [Babelfish](../babelfish/) - Protocol communication

## Contributing

To improve crawlers:
1. Add new detection rules to `tech_detection_rules.json`
2. Implement custom extraction patterns
3. Add support for new authentication methods
4. Improve performance and efficiency
5. Add new use cases and examples

---

**Related Components:**
- [Toolchain](../../) - Execution orchestration
- [Memory](../../../Memory/) - Graph storage
- [Web Security Tools](../web%20security/) - Security analysis
