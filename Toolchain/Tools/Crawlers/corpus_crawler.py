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
from langchain.tools import BaseTool
from langchain_core.callbacks import CallbackManager
from langchain_core.pydantic_v1 import BaseModel, Field
from typing import Optional, Type, List, Dict, Any, Tuple
import argparse
import time
import hashlib
from datetime import datetime

class WebCrawlerConfig:
    """Centralized configuration for the web crawler system."""
    
    def __init__(self, 
                 chroma_path: str = "./Memory/crawl_memory_chroma",
                 html_storage_path: str = "./Output/saved_html",
                 tech_configs_folder: str = "tech_configs",
                 summarize_model: str = "gemma2",
                 tool_model: str = "gemma3:12b"):
        self.chroma_path = chroma_path
        self.html_storage_path = html_storage_path
        self.tech_configs_folder = tech_configs_folder
        self.summarize_model = summarize_model
        self.tool_model = tool_model
        
        # Initialize session
        self.session = requests.Session()
        self.session.headers.update({
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
        
        # Initialize Chroma
        self.chroma_client = chromadb.PersistentClient(path=self.chroma_path)
        self.embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.collection = self.chroma_client.get_or_create_collection(
            name="crawl_memory",
            embedding_function=self.embedding_func
        )
        
        # Initialize LLMs
        self.summarize_llm = Ollama(model=self.summarize_model, temperature=0.0)
        self.tool_llm = Ollama(model=self.tool_model, temperature=0.0)
        
        # Load tech configs
        self.tech_configs = self._load_tech_configs()
    
    def _load_tech_configs(self) -> List[Dict]:
        """Load technology detection configurations from JSON files."""
        techs = []
        if not os.path.exists(self.tech_configs_folder):
            print(f"[Warning] Tech config folder '{self.tech_configs_folder}' does not exist.")
            return techs
        
        for filename in os.listdir(self.tech_configs_folder):
            if filename.endswith(".json"):
                path = os.path.join(self.tech_configs_folder, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        tech = json.load(f)
                        techs.append(tech)
                except Exception as e:
                    print(f"[Error loading {filename}]: {e}")
        
        print(f"[Loaded {len(techs)} tech configs]")
        return techs

class WebPageProcessor:
    """Handles web page processing, analysis, and storage."""
    
    def __init__(self, config: WebCrawlerConfig):
        self.config = config
    
    def safe_get(self, url: str, **kwargs) -> Optional[requests.Response]:
        """Safely fetch a URL with error handling."""
        try:
            r = self.config.session.get(url, timeout=10, **kwargs)
            if r.status_code == 403:
                print(f"[403 Blocked] {url} - trying Common Crawl fallback")
                return None
            r.raise_for_status()
            return r
        except Exception as e:
            print(f"[Live Crawl Error] {url}: {e}")
            return None
    
    def extract_scripts(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        """Extract script information from HTML."""
        soup = BeautifulSoup(html, "html.parser")
        scripts_data = []
        
        for script in soup.find_all("script"):
            if script.get("src"):
                src_url = urljoin(base_url, script["src"])
                scripts_data.append({"src": src_url, "inline": None})
            else:
                inline_js = script.string or ""
                scripts_data.append({
                    "src": None, 
                    "inline": inline_js.strip() if inline_js else ""
                })
        return scripts_data
    
    def detect_technologies(self, html: str, scripts: List[Dict]) -> List[str]:
        """Detect technologies from HTML and scripts using config rules."""
        found_techs = set()
        html_lower = html.lower()

        for tech in self.config.tech_configs:
            name = tech.get("name")
            html_patterns = tech.get("html_patterns", [])
            script_patterns = tech.get("script_patterns", [])

            # Check HTML patterns
            for pat in html_patterns:
                if pat.lower() in html_lower:
                    found_techs.add(name)
                    break

            # Check scripts patterns
            if name not in found_techs:
                for s in scripts:
                    if s.get("src") and any(pat.lower() in s["src"].lower() for pat in script_patterns):
                        found_techs.add(name)
                        break
                    if s.get("inline") and any(pat.lower() in s["inline"].lower() for pat in script_patterns):
                        found_techs.add(name)
                        break
        
        return list(found_techs)
    
    def summarize_page(self, url: str, text: str) -> str:
        """Generate AI summary of page content."""
        preview = text[:5000]
        print(f"[Summarizing Page] {url} - Preview: {preview[:100]}...")
        
        prompt = (
            f"Summarize the content of this webpage. Detail its key features and outline what the domain is used for. "
            f"Skip if the URL is just a section of a larger page.\n\n"
            f"URL: {url}\n\nCONTENT: {preview}"
        )
        
        try:
            summary = self.config.summarize_llm.invoke(prompt).strip()
        except Exception as e:
            summary = f"[Error summarizing page]: {e}"
        
        print(f"[Summarization Result] {summary[:200]}...")
        return summary
    
    def save_html(self, url: str, html: str) -> str:
        """Save HTML content to local storage."""
        domain = urlparse(url).netloc.replace(':', '_')
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        os.makedirs(self.config.html_storage_path, exist_ok=True)
        domain_dir = os.path.join(self.config.html_storage_path, domain)
        os.makedirs(domain_dir, exist_ok=True)

        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        filename = f"{timestamp}_{url_hash}.html"
        filepath = os.path.join(domain_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        
        print(f"[HTML Saved] {filepath}")
        return filepath
    
    def store_in_memory(self, url: str, html: str, scripts: List[Dict], 
                       detected_techs: List[str], summary: str, depth: int):
        """Store processed page data in ChromaDB."""
        metadata = {
            "url": url,
            "depth": depth,
            "detected_technologies": detected_techs,
            "scripts": json.dumps(scripts),
            "indexed_at": datetime.utcnow().isoformat()
        }
        
        try:
            self.config.collection.add(
                ids=[url],
                documents=[summary],
                metadatas=[metadata]
            )
            print(f"[Stored in Chroma] {url} (depth {depth}) with techs: {detected_techs}")
        except Exception as e:
            print(f"[Storage Error] {url}: {e}")
    
    def process_and_store_page(self, url: str, html: str, depth: int) -> Dict[str, Any]:
        """Complete page processing pipeline."""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        
        if len(text) < 50:
            print(f"[Skipped] Content too short at {url}")
            return {"success": False, "reason": "Content too short"}
        
        # Save HTML
        filepath = self.save_html(url, html)
        
        # Extract scripts and detect technologies
        scripts = self.extract_scripts(html, url)
        detected_techs = self.detect_technologies(html, scripts)
        
        # Generate summary
        summary = self.summarize_page(url, text)
        
        # Store in memory
        self.store_in_memory(url, html, scripts, detected_techs, summary, depth)
        
        return {
            "success": True,
            "url": url,
            "filepath": filepath,
            "technologies": detected_techs,
            "scripts": scripts,
            "summary": summary,
            "text_length": len(text)
        }

class CommonCrawlHandler:
    """Handles Common Crawl WARC file processing."""
    
    @staticmethod
    def fetch_common_crawl(url: str) -> Optional[str]:
        """Fetch page content from Common Crawl archives."""
        try:
            index_url = "http://index.commoncrawl.org/collinfo.json"
            idx_list = requests.get(index_url, timeout=15).json()
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

                with open(warc_path, "rb") as stream:
                    for record in ArchiveIterator(stream):
                        if record.rec_type != "response":
                            continue
                        payload = record.content_stream().read()
                        try:
                            html = payload.decode("utf-8", errors="ignore")
                            os.unlink(warc_path)  # Clean up temp file
                            return html
                        except Exception as e:
                            print(f"Decode error: {e}")
                            continue
                            
            except Exception as e:
                print(f"[Common Crawl Error] {e}")
        
        return None

class MemoryManager:
    """Manages ChromaDB memory operations."""
    
    def __init__(self, config: WebCrawlerConfig):
        self.config = config
    
    def recall_from_memory(self, query: str, n_results: int = 5, 
                          min_score: float = 0.3) -> List[Tuple[str, str, float]]:
        """Retrieve relevant information from memory."""
        try:
            results = self.config.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            hits = []
            if results["documents"]:
                for doc, meta, score in zip(
                    results["documents"][0], 
                    results["metadatas"][0], 
                    results["distances"][0]
                ):
                    if score >= min_score:
                        hits.append((meta["url"], doc, score))
            
            return hits
        except Exception as e:
            print(f"[Memory Recall Error] {e}")
            return []
    
    def ensure_context(self, query: str, related_url: str = "", 
                      min_score: float = 0.3) -> List[Tuple[str, str, float]]:
        """Ensure sufficient context exists in memory, crawl if needed."""
        hits = self.recall_from_memory(query, min_score=min_score)
        
        if not hits and related_url:
            print("[Auto-Traversal] Memory too weak, crawling...")
            crawler = WebCrawler(self.config)
            crawler.crawl_hybrid(related_url, max_depth=2)
            hits = self.recall_from_memory(query, min_score=min_score)
        
        return hits

class WebCrawler:
    """Main web crawling functionality."""
    
    def __init__(self, config: WebCrawlerConfig):
        self.config = config
        self.processor = WebPageProcessor(config)
        self.common_crawl = CommonCrawlHandler()
    
    def crawl_live(self, start_url: str, max_depth: int = 2) -> List[Dict[str, Any]]:
        """Crawl live website with depth-first traversal."""
        visited = set()
        queue = deque([(start_url, 0)])
        results = []

        while queue:
            url, depth = queue.popleft()
            if url in visited or depth > max_depth:
                continue
            
            visited.add(url)
            print(f"[Crawling] {url} (depth {depth})")
            
            response = self.processor.safe_get(url)
            if not response:
                continue
            
            result = self.processor.process_and_store_page(url, response.text, depth)
            if result["success"]:
                results.append(result)
            
            # Extract links for further crawling
            if depth < max_depth:
                soup = BeautifulSoup(response.text, "html.parser")
                for a_tag in soup.find_all("a", href=True):
                    link = urljoin(url, a_tag["href"])
                    if (urlparse(link).netloc == urlparse(start_url).netloc and 
                        link not in visited):
                        queue.append((link, depth + 1))
        
        return results
    
    def crawl_hybrid(self, start_url: str, max_depth: int = 2) -> List[Dict[str, Any]]:
        """Hybrid crawling: try live first, fallback to Common Crawl."""
        try:
            return self.crawl_live(start_url, max_depth)
        except Exception as e:
            print(f"[Fallback] Live crawl failed ({e}), trying Common Crawl...")
            html = self.common_crawl.fetch_common_crawl(start_url)
            
            if html:
                result = self.processor.process_and_store_page(start_url, html, 0)
                return [result] if result["success"] else []
            else:
                print(f"[Error] No HTML found for {start_url} in Common Crawl")
                return []

# LangChain Tool Input Schemas
class CrawlWebsiteInput(BaseModel):
    """Input for crawling a website."""
    url: str = Field(description="URL to crawl")
    max_depth: int = Field(default=2, description="Maximum crawl depth")
    use_hybrid: bool = Field(default=True, description="Use hybrid crawling (live + Common Crawl fallback)")

class QueryMemoryInput(BaseModel):
    """Input for querying crawl memory."""
    query: str = Field(description="Search query for retrieving relevant information")
    n_results: int = Field(default=5, description="Number of results to return")
    min_score: float = Field(default=0.3, description="Minimum similarity score")

class NavigateWebInput(BaseModel):
    """Input for web navigation with context awareness."""
    instruction: str = Field(description="Navigation instruction or question about web content")
    target_url: str = Field(default="", description="Optional target URL for focused navigation")
    ensure_context: bool = Field(default=True, description="Automatically crawl if insufficient context")

# LangChain Tools
class CrawlWebsiteTool(BaseTool):
    """LangChain tool for crawling websites."""
    
    name: str = "crawl_website"
    description: str =  (
        "Crawl a website and store its content in memory. "
        "Extracts text, detects technologies, generates summaries, and enables future retrieval. "
        "Supports both live crawling and Common Crawl fallback."
    )
    args_schema: Type[BaseModel] = CrawlWebsiteInput
    
    def __init__(self, config: WebCrawlerConfig):
        super().__init__()
        self.config = config
        self.crawler = WebCrawler(config)
    
    def _run(self, url: str, max_depth: int = 2, use_hybrid: bool = True, 
             run_manager: Optional[CallbackManager] = None) -> str:
        """Execute the crawling operation."""
        try:
            if use_hybrid:
                results = self.crawler.crawl_hybrid(url, max_depth)
            else:
                results = self.crawler.crawl_live(url, max_depth)
            
            if not results:
                return f"Failed to crawl {url}. No content retrieved."
            
            summary_lines = [
                f"Successfully crawled {len(results)} pages from {url}:",
                f"Max depth: {max_depth}"
            ]
            
            for i, result in enumerate(results[:5]):  # Show first 5 results
                techs = ", ".join(result.get("technologies", []))
                summary_lines.append(
                    f"{i+1}. {result['url']} - Technologies: {techs or 'None'}"
                )
            
            if len(results) > 5:
                summary_lines.append(f"... and {len(results) - 5} more pages")
            
            return "\n".join(summary_lines)
            
        except Exception as e:
            return f"Error crawling {url}: {str(e)}"
    
    async def _arun(self, *args, **kwargs):
        """Async version - not implemented."""
        raise NotImplementedError("Async not supported for this tool")

class QueryMemoryTool(BaseTool):
    """LangChain tool for querying crawled content from memory."""
    
    name: str = "query_memory"
    description: str = (
        "Query previously crawled website content from memory. "
        "Returns relevant summaries and metadata based on semantic similarity. "
        "Useful for finding specific information across crawled sites."
    )
    args_schema: Type[BaseModel] = QueryMemoryInput
    
    def __init__(self, config: WebCrawlerConfig):
        super().__init__()
        self.config = config
        self.memory_manager = MemoryManager(config)
    
    def _run(self, query: str, n_results: int = 5, min_score: float = 0.3,
             run_manager: Optional[CallbackManager] = None) -> str:
        """Execute memory query."""
        try:
            hits = self.memory_manager.recall_from_memory(query, n_results, min_score)
            
            if not hits:
                return f"No relevant information found for query: '{query}'"
            
            result_lines = [f"Found {len(hits)} relevant results for '{query}':"]
            
            for i, (url, summary, score) in enumerate(hits, 1):
                result_lines.append(f"\n{i}. {url} (similarity: {score:.2f})")
                result_lines.append(f"   Summary: {summary[:200]}{'...' if len(summary) > 200 else ''}")
            
            return "\n".join(result_lines)
            
        except Exception as e:
            return f"Error querying memory: {str(e)}"
    
    async def _arun(self, *args, **kwargs):
        """Async version - not implemented."""
        raise NotImplementedError("Async not supported for this tool")

class NavigateWebTool(BaseTool):
    """LangChain tool for intelligent web navigation with context awareness."""
    
    name: str = "navigate_web"
    description: str = (
        "Navigate the web intelligently based on instructions. "
        "Automatically ensures sufficient context by crawling if needed. "
        "Can answer questions about web content, find specific information, "
        "and execute complex web-based tasks."
    )
    args_schema: Type[BaseModel] = NavigateWebInput
    
    def __init__(self, config: WebCrawlerConfig):
        super().__init__()
        self.config = config
        self.memory_manager = MemoryManager(config)
        self.crawler = WebCrawler(config)
    
    def _run(self, instruction: str, target_url: str = "", ensure_context: bool = True,
             run_manager: Optional[CallbackManager] = None) -> str:
        """Execute web navigation instruction."""
        try:
            # Extract URLs from instruction if target_url not provided
            if not target_url:
                urls = re.findall(r'https?://[^\s]+', instruction)
                target_url = urls[0] if urls else ""
            
            # Ensure sufficient context
            context_info = ""
            if ensure_context:
                hits = self.memory_manager.ensure_context(instruction, target_url)
                if hits:
                    context_info = "Relevant context from memory:\n"
                    for url, summary, score in hits[:3]:
                        context_info += f"- {url}: {summary[:150]}...\n"
            
            # Prepare prompt for the tool LLM
            prompt_parts = [
                "You are an intelligent web navigation assistant. Based on the context and instruction provided, provide a comprehensive response.",
                f"\nInstruction: {instruction}",
            ]
            
            if target_url:
                prompt_parts.append(f"Target URL: {target_url}")
            
            if context_info:
                prompt_parts.append(f"\nContext:\n{context_info}")
            
            prompt_parts.append(
                "\nProvide a detailed response that addresses the instruction. "
                "If you need more specific information, suggest what should be crawled next."
            )
            
            full_prompt = "\n".join(prompt_parts)
            
            # Execute with tool LLM
            result = self.config.tool_llm.invoke(full_prompt).strip()
            
            return result
            
        except Exception as e:
            return f"Error during web navigation: {str(e)}"
    
    async def _arun(self, *args, **kwargs):
        """Async version - not implemented."""
        raise NotImplementedError("Async not supported for this tool")

class WebCrawlerToolkit:
    """Complete toolkit for web crawling and navigation."""
    
    def __init__(self, config: Optional[WebCrawlerConfig] = None):
        self.config = config or WebCrawlerConfig()
        
        # Initialize tools
        self.crawl_tool = CrawlWebsiteTool(self.config)
        self.query_tool = QueryMemoryTool(self.config)
        self.navigate_tool = NavigateWebTool(self.config)
    
    def get_tools(self) -> List[BaseTool]:
        """Get all tools as a list."""
        return [self.crawl_tool, self.query_tool, self.navigate_tool]
    
    def get_tool_descriptions(self) -> str:
        """Get formatted descriptions of all tools."""
        descriptions = []
        for tool in self.get_tools():
            descriptions.append(f"**{tool.name}**: {tool.description}")
        return "\n".join(descriptions)

# Convenience function for easy initialization
def create_web_crawler_tools(chroma_path: str = "./Memory/crawl_memory_chroma",
                           html_storage_path: str = "./Output/saved_html",
                           tech_configs_folder: str = "tech_configs") -> List[BaseTool]:
    """Create and return web crawler tools with custom configuration."""
    config = WebCrawlerConfig(
        chroma_path=chroma_path,
        html_storage_path=html_storage_path,
        tech_configs_folder=tech_configs_folder
    )
    toolkit = WebCrawlerToolkit(config)
    return toolkit.get_tools()

# Command-line interface for backward compatibility
def main():
    parser = argparse.ArgumentParser(description="Web Crawler + Summarizer + Tech Detector + Tool Executor")
    parser.add_argument("start_url", type=str, help="URL to start crawling from")
    parser.add_argument("--max_depth", type=int, default=2, help="Maximum crawl depth")
    parser.add_argument("--instruction", type=str, 
                       default="Explain the main content and purpose of the website.",
                       help="The navigation instruction for the agent to execute")
    parser.add_argument("--chroma_path", type=str, default="./crawl_memory_chroma",
                       help="Path to ChromaDB storage")
    
    args = parser.parse_args()
    
    # Initialize toolkit
    config = WebCrawlerConfig(chroma_path=args.chroma_path)
    toolkit = WebCrawlerToolkit(config)
    
    print(f"Crawling and analyzing: {args.start_url}")
    
    # Use the tools
    crawl_result = toolkit.crawl_tool._run(args.start_url, args.max_depth)
    print(f"\nCrawl Result:\n{crawl_result}")
    
    navigate_result = toolkit.navigate_tool._run(args.instruction, args.start_url)
    print(f"\nNavigation Result:\n{navigate_result}")

if __name__ == "__main__":
    main()