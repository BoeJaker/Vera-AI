import os
import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque
from warcio.archiveiterator import ArchiveIterator
import chromadb
from chromadb.utils import embedding_functions
import tempfile
import json
import re
from langchain_community.llms import Ollama
import argparse

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/127.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://google.com",
    "Connection": "keep-alive"
})

def safe_get(url, **kwargs):
    try:
        r = session.get(url, timeout=10, **kwargs)
        if r.status_code == 403:
            print(f"[403 Blocked] {url} - trying Common Crawl fallback")
            return None
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"[Live Crawl Error] {url}: {e}")
        return None

# -----------------------
# Chroma Memory Setup
# -----------------------
chroma_client = chromadb.PersistentClient(path="./crawl_memory_chroma")
embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)
collection = chroma_client.get_or_create_collection(
    name="crawl_memory",
    embedding_function=embedding_func
)

# -----------------------
# LLM Setup
# -----------------------
summarize_llm = Ollama(model="gemma2", temperature=0.0)
tool_llm = Ollama(model="gemma3:12b", temperature=0.0)

# -----------------------
# Load tech detection JSON config files
# Each JSON file should have patterns like:
# { "name": "React", "html_patterns": ["react-dom"], "script_patterns": ["react"] }
# -----------------------
def load_tech_configs(folder="tech_configs"):
    techs = []
    if not os.path.exists(folder):
        print(f"[Warning] Tech config folder '{folder}' does not exist.")
        return techs
    for filename in os.listdir(folder):
        if filename.endswith(".json"):
            path = os.path.join(folder, filename)
            with open(path, "r", encoding="utf-8") as f:
                try:
                    tech = json.load(f)
                    techs.append(tech)
                except Exception as e:
                    print(f"[Error loading {filename}]: {e}")
    print(f"[Loaded {len(techs)} tech configs]")
    return techs

TECH_CONFIGS = load_tech_configs()

# -----------------------
# Detect technologies from HTML and scripts using JSON config rules
# -----------------------
def detect_technologies(html, scripts):
    found_techs = set()
    html_lower = html.lower()

    for tech in TECH_CONFIGS:
        name = tech.get("name")
        html_patterns = tech.get("html_patterns", [])
        script_patterns = tech.get("script_patterns", [])

        # Check HTML patterns
        for pat in html_patterns:
            if pat.lower() in html_lower:
                found_techs.add(name)
                break

        # Check scripts patterns in inline scripts or external src urls
        if name not in found_techs:
            for s in scripts:
                # s = {"src": "...", "inline": "..."}
                if s.get("src"):
                    if any(pat.lower() in s["src"].lower() for pat in script_patterns):
                        found_techs.add(name)
                        break
                if s.get("inline"):
                    if any(pat.lower() in s["inline"].lower() for pat in script_patterns):
                        found_techs.add(name)
                        break
    return list(found_techs)

# -----------------------
# Summarization
# -----------------------
def summarize_page(page, text):
    preview = text[:5000]
    print(f"[Summarizing Page] {page} - Preview: {preview[:100]}...")
    prompt = (
        f"Summarize the content of the webpage not the whole website, unless its the base domain. Detail its key features, and outline what the domain is used for, skip if the url is just a section of a larger page.\n\n"
        f"URL: {page}\n\nCONTENT: {preview}"
    )
    try:
        summary = summarize_llm.invoke(prompt).strip()
    except Exception as e:
        summary = f"[Error summarizing page]: {e}"
    print(f"[Summarization Result] {summary[:1000]}...")
    return summary

# -----------------------
# Store in Chroma including html, scripts, detected techs and summary
# -----------------------
def store_in_memory(url, html, scripts, detected_techs, summary, depth):
    metadata = {
        "url": url,
        "depth": depth,
        "detected_technologies": detected_techs,
        "scripts": scripts,
        "indexed_at": __import__("datetime").datetime.utcnow().isoformat()
    }
    collection.add(
        ids=[url],
        documents=[summary],
        metadatas=[metadata]
    )
    print(f"[Stored in Chroma] {url} (depth {depth}) with techs: {detected_techs}")

# -----------------------
# Extract scripts from HTML (inline and external)
# -----------------------
def extract_scripts(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    scripts_data = []
    for script in soup.find_all("script"):
        if script.get("src"):
            # Absolute URL for src
            src_url = urljoin(base_url, script["src"])
            scripts_data.append({"src": src_url, "inline": None})
        else:
            inline_js = script.string or ""
            scripts_data.append({"src": None, "inline": inline_js.strip() if inline_js else ""})
    return scripts_data

# # -----------------------
# # Process HTML Page: Extract, detect tech, summarize, store
# # -----------------------
# def process_and_store_page(url, html, depth):
#     soup = BeautifulSoup(html, "html.parser")
#     text = soup.get_text(separator="\n", strip=True)
#     if len(text) < 50:
#         print(f"[Skipped] Content too short at {url}")
#         return
#     scripts = extract_scripts(html, url)
#     detected_techs = detect_technologies(html, scripts)
#     summary = summarize_page(url, text)
#     store_in_memory(url, html, scripts, detected_techs, summary, depth)

# -----------------------
# Live Site Crawler
# -----------------------
def crawl_live(start_url, max_depth=2):
    visited = set()
    queue = deque([(start_url, 0)])

    while queue:
        url, depth = queue.popleft()
        if url in visited or depth > max_depth:
            continue
        visited.add(url)
        print(f"[Crawling] {url} (depth {depth})")
        try:
            r = safe_get(url)
            if not r:
                continue
            r.raise_for_status()
        except Exception as e:
            print(f"[Live Crawl Error] {url}: {e}")
            continue

        process_and_store_page(url, r.text, depth)

        soup = BeautifulSoup(r.text, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            link = urljoin(url, a_tag["href"])
            # Only same domain crawl
            if urlparse(link).netloc == urlparse(start_url).netloc:
                if link not in visited:
                    queue.append((link, depth + 1))

# -----------------------
# Common Crawl WARC Extraction
# -----------------------
from warcio.archiveiterator import ArchiveIterator
import requests
import tempfile
import json

def fetch_common_crawl(url):
    try:
        index_url = "http://index.commoncrawl.org/collinfo.json"
        idx_list = requests.get(index_url).json()
    except Exception as e:
        print(f"[Common Crawl Error] Failed to fetch index: {e}")
        return None
    print(f"[Common Crawl] Found {len(idx_list)} indices")
    for idx in idx_list:
        api_url = f"{idx['cdx-api']}?url={url}&output=json"
        try:
            r = requests.get(api_url, timeout=10)
            if r.status_code != 200:
                continue
            lines = r.text.strip().split("\n")
            if not lines:
                continue
            print(f"[Common Crawl] Found {len(lines)} entries for {url}")
            entry = json.loads(lines[0])
            
            # Skip crawldiagnostics WARCs
            if "crawldiagnostics" in entry['filename']:
                print(f"[Common Crawl] Skipping crawldiagnostics file: {entry['filename']}")
                continue
            
            warc_url = f"https://commoncrawl.s3.amazonaws.com/{entry['filename']}"
            print(f"[Downloading WARC] {warc_url}")
            
            warc_resp = requests.get(warc_url, stream=True, timeout=20)
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                for chunk in warc_resp.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                warc_path = tmp.name

            with open(warc_path, "rb") as stream:)
                for record in ArchiveIterator(stream):
                    print(f"Record type: {record.rec_type}")
                    if record.rec_type != "response":
                        continue
                    payload = record.content_stream().read()
                    try:
                        html = payload.decode("utf-8", errors="ignore")
                        return html
                    except Exception as e:
                        print(f"Decode error: {e}")
                        continue
        except Exception as e:
            print(f"[Common Crawl Error] {e}")
    return None


# -----------------------
# Hybrid Crawl
# -----------------------
import os
import json
import time
import hashlib

# -----------------------
# HTML Storage
# -----------------------
def save_html(url, html):
    # Prepare directory based on domain
    domain = urlparse(url).netloc.replace(':', '_')
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    base_dir = "./saved_html"
    os.makedirs(base_dir, exist_ok=True)
    domain_dir = os.path.join(base_dir, domain)
    os.makedirs(domain_dir, exist_ok=True)

    # File name: hashed URL + timestamp
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
    filename = f"{timestamp}_{url_hash}.html"
    filepath = os.path.join(domain_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[HTML Saved] {filepath}")
    return filepath

# -----------------------
# Load tech detection rules from JSON
# Example rule: [{"name": "jQuery", "pattern": "jquery.js"}, ...]
# -----------------------
def load_tech_detection_rules(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        rules = json.load(f)
    print(f"[Tech Detection] Loaded {len(rules)} rules from {json_path}")
    return rules

# -----------------------
# Detect tech from HTML using rules
# -----------------------
def detect_technologies(html, rules):
    detected = []
    for rule in rules:
        name = rule.get("name")
        pattern = rule.get("pattern")
        # Simple substring or regex match
        if pattern and re.search(pattern, html, re.I):
            detected.append(name)
    return detected

# -----------------------
# Enhanced process_and_store_page with HTML storage + tech detection
# -----------------------
def process_and_store_page(url, html, depth, tech_rules):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n", strip=True)
    if len(text) < 50:
        return

    # Save HTML locally
    save_html(url, html)

    # Tech detection
    techs = detect_technologies(html, tech_rules)
    tech_summary = ", ".join(techs) if techs else "None detected"
    print(f"[Tech Detection] Technologies detected on {url}: {tech_summary}")

    # Summarize content
    summary = summarize_page(url, text)

    # Append tech info to summary metadata or content
    summary += f"\n\nTechnologies detected: {tech_summary}"

    # Store in vector memory with extra metadata
    collection.add(
        ids=[url],
        documents=[summary],
        metadatas=[{"url": url, "depth": depth, "technologies": techs}]
    )
    print(f"[Stored in Chroma] {url} (depth {depth}) with tech info")

# -----------------------
# Modify crawl_live and crawl_hybrid to pass tech_rules
# -----------------------
def crawl_live(start_url, max_depth, tech_rules):
    visited = set()
    queue = deque([(start_url, 0)])

    while queue:
        url, depth = queue.popleft()
        if url in visited or depth > max_depth:
            continue
        visited.add(url)
        print(f"[Crawling] {url} (depth {depth})")
        r = safe_get(url)
        if not r:
            continue
        process_and_store_page(url, r.text, depth, tech_rules)

        soup = BeautifulSoup(r.text, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            link = urljoin(url, a_tag["href"])
            if urlparse(link).netloc == urlparse(start_url).netloc and link not in visited:
                queue.append((link, depth + 1))


def crawl_hybrid(start_url, max_depth, tech_rules):
    try:
        crawl_live(start_url, max_depth, tech_rules)
    except Exception:
        print("[Fallback] Live crawl failed, trying Common Crawl...")
        html = fetch_common_crawl(start_url)
        print(f"[Common Crawl] Fetched HTML for {start_url}")
        if not html:
            print(f"[Error] No HTML found for {start_url} in Common Crawl")
            return
        if html:
            process_and_store_page(start_url, html, 0, tech_rules)
            return html

# -----------------------
# Recall from Memory
# -----------------------
def recall_from_memory(query, n_results=5, min_score=0.3):
    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    hits = []
    if results["documents"]:
        for doc, meta, score in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
            if score >= min_score:
                hits.append((meta["url"], doc, score))
    return hits

# -----------------------
# Auto-Traversal for Low Context
# -----------------------
def ensure_context(query, related_url, min_score=0.3, tech_rules=None):
    hits = recall_from_memory(query, min_score=min_score)
    if not hits:
        print("[Auto-Traversal] Memory too weak, crawling...")
        crawl_hybrid(related_url, max_depth=2, tech_rules=tech_rules)
        hits = recall_from_memory(query, min_score=min_score)
    return hits

# -----------------------
# ToolExecutor using LangChain Ollama
# -----------------------
class ToolExecutor:
    def __init__(self, llm):
        self.llm = llm

    def run(self, prompt: str) -> str:
        try:
            return self.llm.invoke(prompt).strip()
        except Exception as e:
            return f"[ToolExecutor Error] {e}"
    
# -----------------------
# Agent Execute Actionable
# -----------------------
def execute_actionable(step: str, context: str, html, tool_executor, tech_rules=None):
    print(f"\n[Executing Actionable] {step}")

    urls = re.findall(r'https?://[^\s]+', step)
    related_url = urls[0] if urls else ""
    memory_hits = ensure_context(step, related_url=related_url, tech_rules=tech_rules)
    if memory_hits:
        context += "\n\nRelevant Memory:\n"
        for url, summary, score in memory_hits:
            context += f"\n- {url} (score {score:.2f}): {summary}"

    input_payload = f"Context:\n{context}\n\nTask:\n{step}"

    try:
        result = tool_executor.run(input_payload)
        print(f"[Tool Result] {result}")
        return result
    except Exception as e:
        print(f"[Execution Error] {e}")
        return None    
# -----------------------
# Main update for config loading and passing tech rules
# -----------------------
def main():
    parser = argparse.ArgumentParser(description="Web Crawler + Summarizer + Tech Detector + Tool Executor")
    parser.add_argument("start_url", type=str, help="URL to start crawling from")
    parser.add_argument("--max_depth", type=int, default=2, help="Maximum crawl depth")
    parser.add_argument("--step", type=str, default="Explain the main content and purpose of the website.",
                        help="The actionable step for the agent to execute")
    parser.add_argument("--context", type=str, default="You are an intelligent web assistant.",
                        help="Initial context for the agent")
    parser.add_argument("--tech_config", type=str, default="./tech_detection_rules.json",
                        help="Path to tech detection JSON config file")
    parser.add_argument("--tech_analyze", type=bool, default=False,
                    help="Analyze technologies detected on the page")

    args = parser.parse_args()

    # Load tech detection config
    tech_rules = []
    if os.path.exists(args.tech_config):
        tech_rules = load_tech_detection_rules(args.tech_config)
    else:
        print(f"[Warning] Tech detection config not found: {args.tech_config}")

    print(f"Crawling and summarizing: {args.start_url}")
    page=crawl_hybrid(args.start_url, max_depth=args.max_depth, tech_rules=tech_rules)

    tool_executor = ToolExecutor(tool_llm)
    execute_actionable(args.step, args.context, page, tool_executor, tech_rules=tech_rules)


if __name__ == "__main__":
    main()
