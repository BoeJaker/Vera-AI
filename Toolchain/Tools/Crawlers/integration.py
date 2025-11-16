"""
Web Crawler Integration for tools.py
Add this section to your existing tools.py file
"""

# ============================================================================
# WEB CRAWLER INPUT SCHEMAS
# ============================================================================

class WebCrawlInput(BaseModel):
    """Input schema for web crawling operations."""
    url: str = Field(..., description="URL to crawl")
    max_depth: int = Field(default=2, description="Maximum crawl depth (0-5)")
    use_hybrid: bool = Field(default=True, description="Use hybrid mode (live + Common Crawl fallback)")


class WebMemoryQueryInput(BaseModel):
    """Input schema for querying web crawl memory."""
    query: str = Field(..., description="Search query for crawled content")
    n_results: int = Field(default=5, description="Number of results to return")
    min_score: float = Field(default=0.3, description="Minimum similarity score (0.0-1.0)")


class WebNavigateInput(BaseModel):
    """Input schema for intelligent web navigation."""
    instruction: str = Field(..., description="Navigation instruction or question about web content")
    target_url: Optional[str] = Field(default="", description="Optional target URL")
    ensure_context: bool = Field(default=True, description="Auto-crawl if insufficient context")


class WebTechDetectInput(BaseModel):
    """Input schema for technology detection."""
    url: str = Field(..., description="URL to analyze for technologies")

"""
Web Crawler Integration for tools.py
Add this section to your existing tools.py file
"""

# ============================================================================
# WEB CRAWLER TOOLS CLASS
# ============================================================================
from Vera.Toolchain.Tools.Crawlers.corpus_crawler import WebCrawlerConfig, WebCrawlerToolkit
from Vera.Toolchain.Tools.Crawlers.corpus_crawler import WebPageProcessor

class WebCrawlerTools:
    """Advanced web crawling with memory, technology detection, and Common Crawl fallback."""
    
    def __init__(self, agent):
        self.agent = agent
        
        # Try to initialize web crawler
        try:
            
            # Initialize with integration to agent's memory system
            self.config = WebCrawlerConfig(
                chroma_path="./Memory/crawl_memory_chroma",
                html_storage_path="./Output/saved_html",
                tech_configs_folder="tech_configs",
                summarize_model="gemma2",
                tool_model="gemma3:12b"
            )
            
            self.toolkit = WebCrawlerToolkit(self.config)
            self.available = True
            
            print("[Info] Web Crawler toolkit initialized successfully")
            
        except ImportError:
            self.toolkit = None
            self.config = None
            self.available = False
            print("[Warning] Web Crawler module not available")
    
    def crawl_website(self, url: str, max_depth: int = 2, use_hybrid: bool = True) -> str:
        """
        Crawl a website and store content in searchable memory.
        
        Features:
        - Extracts and stores page content with AI-generated summaries
        - Detects technologies (frameworks, libraries, analytics)
        - Saves HTML locally for reference
        - Falls back to Common Crawl archives if live crawling blocked
        - Depth-first traversal with configurable depth
        
        Technology Detection:
        Automatically detects: React, Vue, Angular, jQuery, WordPress, 
        Google Analytics, Bootstrap, Tailwind, Next.js, and more.
        
        Memory Storage:
        All crawled content stored in ChromaDB with semantic search.
        Use query_crawl_memory to retrieve information later.
        
        Args:
            url: Starting URL to crawl
            max_depth: How many link levels deep to crawl (0-5)
            use_hybrid: Use Common Crawl fallback if live fails
        
        Returns:
            Summary of crawled pages with detected technologies
        
        Example:
            crawl_website(
                url="https://docs.python.org/3/",
                max_depth=2,
                use_hybrid=True
            )
        """
        if not self.available:
            return "[Error] Web Crawler not available. Install dependencies: warcio chromadb sentence-transformers beautifulsoup4"
        
        try:
            # Execute crawl
            result = self.toolkit.crawl_tool._run(
                url=url,
                max_depth=max_depth,
                use_hybrid=use_hybrid
            )
            
            # Integrate with agent memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                url,
                "web_crawl",
                metadata={
                    "url": url,
                    "max_depth": max_depth,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            )
            
            return result
            
        except Exception as e:
            return f"[Crawl Error] {str(e)}\n{traceback.format_exc()}"
    
    def query_crawl_memory(self, query: str, n_results: int = 5, 
                          min_score: float = 0.3) -> str:
        """
        Search previously crawled website content using semantic similarity.
        
        Uses ChromaDB vector search to find relevant content from all
        crawled pages. Returns summaries with URLs and similarity scores.
        
        Perfect for:
        - Finding specific documentation pages
        - Discovering related content across sites
        - Answering questions about crawled websites
        - Technology stack research
        
        Args:
            query: What you're looking for (natural language)
            n_results: Max number of results to return
            min_score: Minimum similarity threshold (0.0-1.0)
        
        Returns:
            Ranked list of relevant pages with summaries
        
        Example:
            query_crawl_memory(
                query="How do I use async/await in Python?",
                n_results=5,
                min_score=0.4
            )
        """
        if not self.available:
            return "[Error] Web Crawler not available"
        
        try:
            result = self.toolkit.query_tool._run(
                query=query,
                n_results=n_results,
                min_score=min_score
            )
            
            # Log query to agent memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                query,
                "crawl_memory_query",
                metadata={"n_results": n_results, "min_score": min_score}
            )
            
            return result
            
        except Exception as e:
            return f"[Query Error] {str(e)}"
    
    def navigate_web_intelligent(self, instruction: str, target_url: str = "",
                                ensure_context: bool = True) -> str:
        """
        Intelligent web navigation with automatic context building.
        
        This is an AI-powered web research assistant that:
        - Understands natural language instructions
        - Automatically crawls sites if context is insufficient
        - Synthesizes information from multiple pages
        - Answers complex questions about web content
        - Suggests next steps for deeper research
        
        The agent will:
        1. Check existing memory for relevant context
        2. Auto-crawl target URL if needed and ensure_context=True
        3. Use LLM to synthesize a comprehensive answer
        4. Provide source URLs and suggest follow-up actions
        
        Args:
            instruction: What you want to know or do
            target_url: Optional specific URL to focus on
            ensure_context: Auto-crawl if insufficient memory
        
        Returns:
            Comprehensive answer with sources
        
        Examples:
            navigate_web_intelligent(
                instruction="Explain how to install and use FastAPI with async database connections"
            )
            
            navigate_web_intelligent(
                instruction="What are the main features?",
                target_url="https://fastapi.tiangolo.com",
                ensure_context=True
            )
        """
        if not self.available:
            return "[Error] Web Crawler not available"
        
        try:
            result = self.toolkit.navigate_tool._run(
                instruction=instruction,
                target_url=target_url,
                ensure_context=ensure_context
            )
            
            # Store navigation action in agent memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                instruction,
                "web_navigation",
                metadata={
                    "target_url": target_url,
                    "ensure_context": ensure_context
                }
            )
            
            return result
            
        except Exception as e:
            return f"[Navigation Error] {str(e)}"
    
    def detect_technologies(self, url: str) -> str:
        """
        Detect technologies used on a website.
        
        Analyzes HTML, scripts, and resources to identify:
        - Frontend frameworks (React, Vue, Angular, Svelte)
        - CSS frameworks (Bootstrap, Tailwind, Material-UI)
        - Build tools (Webpack, Vite, Next.js, Nuxt)
        - Analytics (Google Analytics, Mixpanel, Segment)
        - CDNs and hosting platforms
        - CMS systems (WordPress, Drupal, etc.)
        - And many more...
        
        Detection uses pattern matching against:
        - HTML content and meta tags
        - JavaScript files and inline scripts
        - Link tags and resource URLs
        
        Args:
            url: URL to analyze
        
        Returns:
            List of detected technologies with confidence
        
        Example:
            detect_technologies("https://github.com")
        """
        if not self.available:
            return "[Error] Web Crawler not available"
        
        try:
            # Use the crawler's technology detection            
            processor = WebPageProcessor(self.config)
            response = processor.safe_get(url)
            
            if not response:
                return f"[Error] Could not fetch {url}"
            
            # Extract and analyze
            scripts = processor.extract_scripts(response.text, url)
            technologies = processor.detect_technologies(response.text, scripts)
            
            if not technologies:
                return f"No technologies detected on {url}"
            
            # Format output
            output = [f"Technologies detected on {url}:"]
            for tech in sorted(technologies):
                output.append(f"  ✓ {tech}")
            
            # Store in agent memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                url,
                "tech_detection",
                metadata={
                    "url": url,
                    "technologies": technologies
                }
            )
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Detection Error] {str(e)}"
    
    def list_crawled_sites(self, limit: int = 20) -> str:
        """
        List recently crawled websites from memory.
        
        Shows all sites that have been crawled and stored,
        with their metadata and crawl timestamps.
        
        Args:
            limit: Maximum number of sites to list
        
        Returns:
            Formatted list of crawled sites
        """
        if not self.available:
            return "[Error] Web Crawler not available"
        
        try:
            collection = self.config.collection
            
            # Get all documents (ChromaDB doesn't have a simple "list all" but we can peek)
            results = collection.peek(limit=limit)
            
            if not results["ids"]:
                return "No crawled sites in memory yet."
            
            output = [f"Recently crawled sites ({len(results['ids'])} total):"]
            
            for i, (url, metadata) in enumerate(zip(results["ids"], results["metadatas"]), 1):
                techs = metadata.get("detected_technologies", [])
                depth = metadata.get("depth", "?")
                indexed = metadata.get("indexed_at", "unknown")
                
                output.append(f"\n{i}. {url}")
                output.append(f"   Depth: {depth} | Indexed: {indexed[:10]}")
                if techs:
                    output.append(f"   Technologies: {', '.join(techs[:5])}")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[List Error] {str(e)}"
    
    def clear_crawl_memory(self, confirm: bool = False) -> str:
        """
        Clear all crawled website data from memory.
        
        WARNING: This permanently deletes all crawled content,
        summaries, and metadata from ChromaDB.
        
        Args:
            confirm: Must be True to actually clear memory
        
        Returns:
            Confirmation message
        """
        if not self.available:
            return "[Error] Web Crawler not available"
        
        if not confirm:
            return "[Safety] Set confirm=True to actually clear memory. This cannot be undone!"
        
        try:
            # Delete and recreate collection
            self.config.chroma_client.delete_collection("crawl_memory")
            self.config.collection = self.config.chroma_client.create_collection(
                name="crawl_memory",
                embedding_function=self.config.embedding_func
            )
            
            return "✓ Crawl memory cleared successfully"
            
        except Exception as e:
            return f"[Clear Error] {str(e)}"

