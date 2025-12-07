from langchain.agents import Tool
from langchain_core.tools import tool, StructuredTool
from langchain.tools import BaseTool
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain_community.tools.playwright.utils import create_async_playwright_browser

import os
import subprocess
import sys
import io
import traceback
import asyncio
import re
import json
import sqlite3
import requests
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus, urlparse
from typing import List, Dict, Any, Type, Optional, Union
from pydantic import BaseModel, Field
from functools import partial
from contextlib import contextmanager

from duckduckgo_search import DDGS
from playwright.async_api import async_playwright

# MCP Client imports (install: pip install mcp anthropic-mcp-client)
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("[Warning] MCP not available. Install with: pip install mcp anthropic-mcp-client")

from Vera.Toolchain.Tools.protocols import add_ssh_postgres_neo4j_tools
from Vera.Toolchain.schemas import *
import Vera.Toolchain.dynamic_tools as DynamicTools
from Vera.Toolchain.mcp_manager import *
from Vera.Toolchain.Tools.code_executor import *
from Vera.Toolchain.Tools.Microcontrollers.microcontollers2 import *
from Vera.Toolchain.Tools.version_manager import *
from Vera.Toolchain.n8n_tools import *
from Vera.Toolchain.Tools.Memory.memory_advanced_pt2 import *
from Vera.Toolchain.Tools.Memory.memory_advanced import *
from Vera.Toolchain.Tools.Memory.memory import *
from Vera.Toolchain.Tools.orchestration import *
from Vera.Toolchain.Tools.OSINT.loader import add_all_osint_tools

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

@contextmanager
def redirect_stdout():
    """Context manager for safely redirecting stdout."""
    old_stdout = sys.stdout
    redirected_output = sys.stdout = io.StringIO()
    try:
        yield redirected_output
    finally:
        sys.stdout = old_stdout


def sanitize_path(path: str) -> str:
    """Sanitize and validate file paths."""
    path = os.path.normpath(path)
    if path.startswith('..'):
        raise ValueError("Path traversal not allowed")
    return path


def truncate_output(text: str, max_length: int = 5000) -> str:
    """Truncate long outputs with indication."""
    if len(text) > max_length:
        return text[:max_length] + f"\n... [truncated {len(text) - max_length} characters]"
    return text


def format_json(data: Any) -> str:
    """Format data as pretty JSON."""
    try:
        return json.dumps(data, indent=2, default=str)
    except:
        return str(data)


# ============================================================================
# MCP CLIENT MANAGER
# ============================================================================

class MCPManager:
    """Manages MCP server connections and tool invocations."""
    
    def __init__(self):
        self.servers: Dict[str, Any] = {}
        self.sessions: Dict[str, ClientSession] = {}
        
    async def connect_server(self, name: str, command: str, args: List[str] = None, env: Dict[str, str] = None):
        """Connect to an MCP server."""
        if not MCP_AVAILABLE:
            raise RuntimeError("MCP not available. Install with: pip install mcp anthropic-mcp-client")
        
        server_params = StdioServerParameters(
            command=command,
            args=args or [],
            env=env
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                self.servers[name] = server_params
                self.sessions[name] = session
                return f"Connected to MCP server: {name}"
    
    async def list_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """List available tools from an MCP server."""
        if server_name not in self.sessions:
            raise ValueError(f"Server {server_name} not connected")
        
        session = self.sessions[server_name]
        response = await session.list_tools()
        return [{"name": tool.name, "description": tool.description} for tool in response.tools]
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool on an MCP server."""
        if server_name not in self.sessions:
            raise ValueError(f"Server {server_name} not connected")
        
        session = self.sessions[server_name]
        result = await session.call_tool(tool_name, arguments)
        return format_json(result)


# ============================================================================
# CORE TOOL IMPLEMENTATIONS
# ============================================================================

class LLMTools:
    """Organized collection of LLM tools with proper error handling and memory integration."""
    
    def __init__(self, agent):
        self.agent = agent
        self.mcp_manager = MCPManager() if MCP_AVAILABLE else None
        
    # ------------------------------------------------------------------------
    # LLM INTERACTION TOOLS
    # ------------------------------------------------------------------------
    
    def fast_llm_query(self, query: str) -> str:
        """
        Query a fast LLM for quick tasks like summarization, simple analysis.
        Best for: creative writing, text review, summarization, combining text.
        Note: Fast but can be less accurate than deep LLM.
        """
        try:
            result = ""
            for chunk in self.agent.stream_llm_with_memory(
                self.agent.fast_llm, query, long_term=False, short_term=True
            ):
                text = chunk if isinstance(chunk, str) else str(chunk)
                result += text
            
            self.agent.mem.add_session_memory(
                self.agent.sess.id, result, "Answer", 
                {"topic": "fast_llm", "agent": self.agent.selected_models["fast_llm"]}
            )
            return result
        except Exception as e:
            return f"[Fast LLM Error] {str(e)}"

    def deep_llm_query(self, query: str) -> str:
        """
        Query a deep LLM for complex reasoning and detailed analysis.
        Best for: complex reasoning, detailed analysis, accuracy-critical tasks.
        Note: Slower but more accurate than fast LLM.
        """
        try:
            result = ""
            for chunk in self.agent.stream_llm_with_memory(
                self.agent.deep_llm, query, long_term=True, short_term=True
            ):
                text = chunk if isinstance(chunk, str) else str(chunk)
                result += text
            
            self.agent.mem.add_session_memory(
                self.agent.sess.id, result, "Answer",
                {"topic": "deep_llm", "agent": self.agent.selected_models["deep_llm"]}
            )
            return result
        except Exception as e:
            return f"[Deep LLM Error] {str(e)}"
    
    # ------------------------------------------------------------------------
    # FILE SYSTEM TOOLS
    # ------------------------------------------------------------------------
    
    def read_file(self, path: str) -> str:
        """
        Read and return the contents of a file.
        Supports text files of any format.
        """
        try:
            path = sanitize_path(path)
            
            if not os.path.exists(path):
                return f"[Error] File not found: {path}"
            
            if not os.path.isfile(path):
                return f"[Error] Path is not a file: {path}"
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Add to memory
            m1 = self.agent.mem.add_session_memory(
                self.agent.sess.id, path, "file",
                metadata={"status": "active", "priority": "high"},
                labels=["File"], promote=True
            )
            m2 = self.agent.mem.attach_document(
                self.agent.sess.id, path, content,
                {"topic": "read_file", "agent": "system"}
            )
            self.agent.mem.link(m1.id, m2.id, "Read")
            
            return truncate_output(content)
            
        except UnicodeDecodeError:
            return f"[Error] File is not a text file or has encoding issues: {path}"
        except Exception as e:
            return f"[Error] Failed to read file: {str(e)}"

    def write_file(self, path: str, content: str) -> str:
        """
        Write content to a file. Creates parent directories if needed.
        Overwrites existing files.
        """
        try:
            path = sanitize_path(path)
            
            # Create parent directories if they don't exist
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Add to memory
            m1 = self.agent.mem.add_session_memory(
                self.agent.sess.id, path, "file",
                metadata={"status": "active", "priority": "high"},
                labels=["File"], promote=True
            )
            m2 = self.agent.mem.attach_document(
                self.agent.sess.id, path, content,
                {"topic": "write_file", "agent": "system"}
            )
            self.agent.mem.link(m1.id, m2.id, "Written")
            
            return f"Successfully wrote {len(content)} characters to {path}"
            
        except Exception as e:
            return f"[Error] Failed to write file: {str(e)}"
    
    def list_directory(self, path: str = ".") -> str:
        """
        List contents of a directory with file sizes and types.
        """
        try:
            path = sanitize_path(path)
            
            if not os.path.exists(path):
                return f"[Error] Directory not found: {path}"
            
            if not os.path.isdir(path):
                return f"[Error] Path is not a directory: {path}"
            
            items = []
            for item in sorted(os.listdir(path)):
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    items.append(f"[DIR]  {item}/")
                else:
                    size = os.path.getsize(item_path)
                    items.append(f"[FILE] {item} ({size} bytes)")
            
            return "\n".join(items) if items else "[Empty directory]"
            
        except Exception as e:
            return f"[Error] Failed to list directory: {str(e)}"
    
    def search_files(self, path: str, pattern: str) -> str:
        """
        Search for files matching a pattern recursively.
        Pattern can be a glob pattern (*.py) or regex.
        """
        try:
            path = sanitize_path(path)
            matches = []
            
            for root, dirs, files in os.walk(path):
                for file in files:
                    if re.search(pattern, file) or file.endswith(pattern):
                        full_path = os.path.join(root, file)
                        size = os.path.getsize(full_path)
                        matches.append(f"{full_path} ({size} bytes)")
            
            return "\n".join(matches) if matches else f"No files matching '{pattern}' found"
            
        except Exception as e:
            return f"[Error] Failed to search files: {str(e)}"
    
    # ------------------------------------------------------------------------
    # CODE EXECUTION TOOLS
    # ------------------------------------------------------------------------
    
    def run_python(self, code: str) -> str:
        """
        Execute Python code in a controlled environment.
        Use print() to output results. Both eval and exec are supported.
        """
        try:
            with redirect_stdout() as redirected_output:
                local_vars = {}
                
                try:
                    # Try eval first for expressions
                    result = eval(code, globals(), local_vars)
                    if result is not None:
                        print(result)
                except SyntaxError:
                    # Fall back to exec for statements
                    exec(code, globals(), local_vars)
                
                output = redirected_output.getvalue()
            
            # Add to memory
            m1 = self.agent.mem.upsert_entity(
                code, "python",
                labels=["Python"],
                properties={"language": "python", "priority": "high"}
            )
            m2 = self.agent.mem.add_session_memory(
                self.agent.sess.id, code, "Python",
                {"topic": "python_execution", "agent": "system"}
            )
            self.agent.mem.link(m1.id, m2.id, "Executed")
            
            if output:
                m3 = self.agent.mem.add_session_memory(
                    self.agent.sess.id, output, "PythonOutput",
                    {"topic": "python_result", "agent": "system"}
                )
                self.agent.mem.link(m1.id, m3.id, "Output")
            
            return truncate_output(output.strip() or "[No output]")
            
        except Exception as e:
            error_trace = traceback.format_exc()
            return f"[Python Error]\n{truncate_output(error_trace)}"

    def run_bash_command(self, command: str) -> str:
        """
        Execute a bash shell command and return output.
        Warning: Use with caution. Commands have full system access.
        """
        try:
            result = subprocess.check_output(
                command,
                shell=True,
                text=True,
                stderr=subprocess.STDOUT,
                timeout=30  # 30 second timeout
            )
            
            # Add to memory
            m1 = self.agent.mem.upsert_entity(
                command, "command",
                labels=["Command"],
                properties={"shell": "bash", "priority": "high"}
            )
            m2 = self.agent.mem.add_session_memory(
                self.agent.sess.id, command, "Command",
                {"topic": "bash_command", "agent": "system"}
            )
            self.agent.mem.link(m1.id, m2.id, "Executed")
            
            m3 = self.agent.mem.add_session_memory(
                self.agent.sess.id, result, "CommandOutput",
                {"topic": "bash_output", "agent": "system"}
            )
            self.agent.mem.link(m1.id, m3.id, "Output")
            
            return truncate_output(result)
            
        except subprocess.TimeoutExpired:
            return "[Error] Command timed out after 30 seconds"
        except subprocess.CalledProcessError as e:
            return f"[Error] Command failed with exit code {e.returncode}\n{e.output}"
        except Exception as e:
            return f"[Error] Failed to execute command: {str(e)}"
    
    # ------------------------------------------------------------------------
    # WEB SEARCH TOOLS
    # ------------------------------------------------------------------------
    
    async def _playwright_search(self, query: str, search_engine: str, max_results: int) -> List[Dict[str, str]]:
        """
        Perform web search using Playwright for maximum robustness.
        Supports multiple search engines with fallback mechanisms.
        """
        search_configs = {
            "google": {
                "url": f"https://www.google.com/search?q={quote_plus(query)}",
                "result_selector": "div.g",
                "title_selector": "h3",
                "link_selector": "a",
                "snippet_selector": "div[data-sncf], div.VwiC3b, span.aCOpRe"
            },
            "bing": {
                "url": f"https://www.bing.com/search?q={quote_plus(query)}",
                "result_selector": "li.b_algo",
                "title_selector": "h2",
                "link_selector": "a",
                "snippet_selector": "p, .b_caption p"
            },
            "duckduckgo": {
                "url": f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
                "result_selector": "div.result",
                "title_selector": "a.result__a",
                "link_selector": "a.result__a",
                "snippet_selector": "a.result__snippet"
            },
            "brave": {
                "url": f"https://search.brave.com/search?q={quote_plus(query)}",
                "result_selector": "div.snippet",
                "title_selector": "div.title",
                "link_selector": "a",
                "snippet_selector": "div.snippet-description"
            },
            "perplexity": {
                "url": f"https://www.perplexity.ai/search?q={quote_plus(query)}",
                "result_selector": "div[class*='result'], div[class*='Result']",
                "title_selector": "a, h3",
                "link_selector": "a",
                "snippet_selector": "div[class*='snippet'], p"
            }
        }
        
        config = search_configs.get(search_engine.lower())
        if not config:
            raise ValueError(f"Unsupported search engine: {search_engine}")
        
        results = []
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled']
                )
                
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    locale='en-US'
                )
                
                # Add stealth settings
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)
                
                page = await context.new_page()
                
                # Navigate to search page
                await page.goto(config["url"], wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)
                
                # Handle cookie consent dialogs
                consent_selectors = [
                    'button:has-text("Accept")',
                    'button:has-text("Agree")',
                    'button:has-text("I agree")',
                    'button:has-text("Accept all")',
                    '[aria-label*="accept" i]',
                    '#L2AGLb',  # Google specific
                    'button[id*="accept"]',
                    'button[class*="accept"]'
                ]
                
                for selector in consent_selectors:
                    try:
                        button = await page.query_selector(selector)
                        if button and await button.is_visible():
                            await button.click()
                            await page.wait_for_timeout(1000)
                            break
                    except:
                        continue
                
                # Wait for results to load
                try:
                    await page.wait_for_selector(config["result_selector"], timeout=10000)
                except:
                    # If primary selector fails, try to wait for any content
                    await page.wait_for_timeout(3000)
                
                # Extract search results
                result_elements = await page.query_selector_all(config["result_selector"])
                
                for idx, result_elem in enumerate(result_elements[:max_results]):
                    try:
                        # Extract title
                        title = ""
                        title_elem = await result_elem.query_selector(config["title_selector"])
                        if title_elem:
                            title = await title_elem.inner_text()
                            title = title.strip()
                        
                        # Extract URL
                        url = ""
                        link_elem = await result_elem.query_selector(config["link_selector"])
                        if link_elem:
                            url = await link_elem.get_attribute('href')
                            
                            # Clean up URL
                            if url:
                                # Handle relative URLs
                                if url.startswith('/'):
                                    parsed = urlparse(config["url"])
                                    url = f"{parsed.scheme}://{parsed.netloc}{url}"
                                
                                # Handle DuckDuckGo redirect URLs
                                if 'duckduckgo.com' in url and '/l/?uddg=' in url:
                                    try:
                                        from urllib.parse import unquote
                                        url = unquote(url.split('/l/?uddg=')[1].split('&')[0])
                                    except:
                                        pass
                                
                                # Handle Google redirect URLs
                                if 'google.com' in config["url"] and '/url?q=' in url:
                                    try:
                                        url = url.split('/url?q=')[1].split('&')[0]
                                        from urllib.parse import unquote
                                        url = unquote(url)
                                    except:
                                        pass
                        
                        # Extract snippet/description
                        snippet = ""
                        snippet_elem = await result_elem.query_selector(config["snippet_selector"])
                        if snippet_elem:
                            snippet = await snippet_elem.inner_text()
                            snippet = snippet.strip()
                        
                        # Only add if we have at least a title and URL
                        if title and url and url.startswith('http'):
                            results.append({
                                "title": title,
                                "href": url,
                                "body": snippet
                            })
                    
                    except Exception as e:
                        # Skip individual result errors
                        continue
                
                await browser.close()
                
        except Exception as e:
            raise Exception(f"Search failed for {search_engine}: {str(e)}")
        
        return results

    def search_web(self, query: str, max_results: int = 10, search_engine: str = "duckduckgo") -> str:
        """
        Advanced web search using Playwright for robustness.
        Supports multiple search engines with automatic fallback.
        
        Search engines: duckduckgo (default), google, bing, brave, perplexity
        Returns titles, URLs, and descriptions from search results.
        
        Features:
        - Bypasses bot detection
        - Handles cookie consent
        - Extracts clean URLs
        - Falls back to alternative engines on failure
        """
        search_engine = search_engine.lower()
        
        # Define fallback order
        fallback_engines = {
            "google": ["duckduckgo", "bing"],
            "bing": ["duckduckgo", "google"],
            "duckduckgo": ["bing", "brave"],
            "brave": ["duckduckgo", "bing"],
            "perplexity": ["duckduckgo", "bing"]
        }
        
        engines_to_try = [search_engine] + fallback_engines.get(search_engine, ["duckduckgo"])
        
        results = []
        last_error = None
        
        # Setup event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Try each engine in order
        for engine in engines_to_try:
            try:
                results = loop.run_until_complete(
                    self._playwright_search(query, engine, max_results)
                )
                
                if results:
                    search_engine = engine  # Update to successful engine
                    break
                    
            except Exception as e:
                last_error = str(e)
                continue
        
        # If all engines failed
        if not results:
            return f"[Search Error] All search engines failed. Last error: {last_error}"
        
        try:
            # Store in memory
            search_mem = self.agent.mem.add_session_memory(
                self.agent.sess.id, query, "web_search",
                metadata={"search_engine": search_engine, "type": "playwright_search"}
            )
            
            output = []
            for idx, r in enumerate(results, 1):
                title = r.get("title", "No title")
                href = r.get("href", "")
                body = r.get("body", "No description")
                
                # Store result in memory
                result_entity = self.agent.mem.upsert_entity(
                    href, "search_result",
                    properties={"title": title, "body": body, "engine": search_engine},
                    labels=["SearchResult"]
                )
                self.agent.mem.link(search_mem.id, result_entity.id, "RESULT")
                
                output.append(f"{idx}. {title}\n   URL: {href}\n   {body}\n")
            
            # Add metadata footer
            footer = f"\n[Searched using {search_engine.title()} • {len(results)} results found]"
            
            return "\n".join(output) + footer
            
        except Exception as e:
            # Return results even if memory storage fails
            output = []
            for idx, r in enumerate(results, 1):
                output.append(f"{idx}. {r.get('title', 'No title')}\n   URL: {r.get('href', '')}\n   {r.get('body', '')}\n")
            return "\n".join(output)

    def search_news(self, query: str, max_results: int = 10) -> str:
        """
        Search for recent news articles using DuckDuckGo News.
        Best for current events and recent developments.
        """
        try:
            with DDGS() as ddgs:
                results = ddgs.news(query, region="us-en", max_results=max_results)
                
                search_mem = self.agent.mem.add_session_memory(
                    self.agent.sess.id, query, "news_search",
                    metadata={"search_engine": "duckduckgo", "type": "news"}
                )
                
                output = []
                for idx, r in enumerate(results, 1):
                    title = r.get("title", "No title")
                    href = r.get("url", "")
                    body = r.get("body", "No description")
                    date = r.get("date", "Unknown date")
                    
                    result_entity = self.agent.mem.upsert_entity(
                        href, "news_result",
                        properties={"title": title, "body": body, "date": date},
                        labels=["NewsResult"]
                    )
                    self.agent.mem.link(search_mem.id, result_entity.id, "RESULT")
                    
                    output.append(f"{idx}. [{date}] {title}\n   URL: {href}\n   {body}\n")
                
                return "\n".join(output) if output else "No news found."
                
        except Exception as e:
            return f"[News Search Error] {str(e)}"

    async def _scrape_url(self, url: str) -> str:
        """Helper method to scrape a single URL using Playwright."""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                page = await context.new_page()
                
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(2000)
                
                # Handle cookie consent
                consent_selectors = [
                    'button:has-text("Accept")',
                    'button:has-text("Agree")',
                    '[aria-label*="accept" i]'
                ]
                
                for selector in consent_selectors:
                    try:
                        button = await page.query_selector(selector)
                        if button and await button.is_visible():
                            await button.click()
                            await page.wait_for_timeout(1000)
                            break
                    except:
                        continue
                
                # Extract content
                content_selectors = [
                    'article', 'main', '[role="main"]',
                    '.article', '.content', '.post'
                ]
                
                content_text = ""
                for selector in content_selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            text = await element.inner_text()
                            if len(text) > 200:
                                content_text = text
                                break
                    except:
                        continue
                
                # Fallback to paragraphs
                if len(content_text) < 200:
                    paragraphs = await page.query_selector_all('p')
                    para_texts = []
                    for p in paragraphs:
                        try:
                            text = await p.inner_text()
                            if len(text) > 50:
                                para_texts.append(text)
                        except:
                            continue
                    content_text = '\n\n'.join(para_texts)
                
                await browser.close()
                
                # Clean text
                lines = (line.strip() for line in content_text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                cleaned = ' '.join(chunk for chunk in chunks if chunk)
                cleaned = re.sub(r'\s+', ' ', cleaned).strip()
                
                return truncate_output(cleaned, 2500) if cleaned else "[No content extracted]"
                
        except Exception as e:
            return f"[Scraping Error: {str(e)[:100]}]"

    def web_search_deep(self, input_data: str, max_results: int = 5) -> str:
        """
        Comprehensive web search that scrapes full page content.
        Accepts search queries or existing search result text.
        Returns detailed reports with full page content from each result.
        Use when you need in-depth information from web pages.
        """
        try:
            # Determine if input is query or existing results
            if re.search(r'^\d+\.\s+.+', input_data) and 'http' in input_data:
                results = self._parse_search_results(input_data)
                search_query = "parsed_results"
            else:
                with DDGS() as ddgs:
                    results = list(ddgs.text(input_data, region="us-en", max_results=max_results))
                search_query = input_data
            
            if not results:
                return "No results to process."
            
            # Create memory entry
            search_mem = self.agent.mem.add_session_memory(
                self.agent.sess.id, search_query, "deep_web_search",
                metadata={"type": "deep_search", "max_results": max_results}
            )
            
            # Setup event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            output = []
            for idx, r in enumerate(results[:max_results], 1):
                title = r.get("title", "No title")
                href = r.get("href", "")
                body = r.get("body", "")
                
                if not href:
                    continue
                
                # Store result
                result_entity = self.agent.mem.upsert_entity(
                    href, "deep_search_result",
                    properties={"title": title, "body": body},
                    labels=["DeepSearchResult"]
                )
                self.agent.mem.link(search_mem.id, result_entity.id, "RESULT")
                
                # Scrape content
                output.append(f"\n{'='*80}\nRESULT {idx}: {title}\nURL: {href}\nDescription: {body}\n{'-'*40}")
                
                scraped = loop.run_until_complete(self._scrape_url(href))
                output.append(f"Content:\n{scraped}\n{'='*80}")
                
                # Store scraped content
                content_entity = self.agent.mem.upsert_entity(
                    f"{href}_content", "scraped_content",
                    properties={"title": title, "url": href, "preview": scraped[:500]},
                    labels=["ScrapedContent"]
                )
                self.agent.mem.link(result_entity.id, content_entity.id, "HAS_CONTENT")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Deep Search Error] {str(e)}"

    def _parse_search_results(self, text: str) -> List[Dict[str, str]]:
        """Parse search results from text format."""
        results = []
        lines = text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            if re.match(r'^\d+\.\s+.+', line):
                title = line.split('. ', 1)[1] if '. ' in line else line
                url = lines[i + 1].strip() if i + 1 < len(lines) and lines[i + 1].startswith('http') else ""
                body = lines[i + 2].strip() if i + 2 < len(lines) else ""
                
                if url:
                    results.append({"title": title, "href": url, "body": body})
                i += 3
            else:
                i += 1
        
        return results
    
    # ------------------------------------------------------------------------
    # HTTP/API TOOLS
    # ------------------------------------------------------------------------
    
    def http_request(self, url: str, method: str = "GET", headers: Optional[Dict] = None, body: Optional[str] = None) -> str:
        """
        Make HTTP requests to APIs or web services.
        Supports GET, POST, PUT, DELETE methods.
        """
        try:
            method = method.upper()
            headers = headers or {}
            
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, data=body, timeout=30)
            elif method == "PUT":
                response = requests.put(url, headers=headers, data=body, timeout=30)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                return f"[Error] Unsupported method: {method}"
            
            result = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text[:5000]  # Truncate large responses
            }
            
            return format_json(result)
            
        except Exception as e:
            return f"[HTTP Error] {str(e)}"
    
    # ------------------------------------------------------------------------
    # DATABASE TOOLS
    # ------------------------------------------------------------------------
    
    def sqlite_query(self, db_path: str, query: str) -> str:
        """
        Execute SQLite queries. Supports SELECT, INSERT, UPDATE, DELETE.
        Returns formatted results.
        """
        try:
            db_path = sanitize_path(db_path)
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute(query)
            
            if query.strip().upper().startswith("SELECT"):
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                result = {"columns": columns, "rows": rows, "count": len(rows)}
                output = format_json(result)
            else:
                conn.commit()
                output = f"Query executed successfully. Rows affected: {cursor.rowcount}"
            
            conn.close()
            return output
            
        except Exception as e:
            return f"[SQLite Error] {str(e)}"
    
    # ------------------------------------------------------------------------
    # GIT TOOLS
    # ------------------------------------------------------------------------
    
    def git_operation(self, repo_path: str = ".", command: str = "status", args: str = "") -> str:
        """
        Execute git commands in a repository.
        Supports: status, log, diff, branch, add, commit, push, pull, etc.
        """
        try:
            repo_path = sanitize_path(repo_path)
            
            full_command = f"git -C {repo_path} {command} {args}"
            
            result = subprocess.check_output(
                full_command,
                shell=True,
                text=True,
                stderr=subprocess.STDOUT,
                timeout=30
            )
            
            return truncate_output(result)
            
        except subprocess.CalledProcessError as e:
            return f"[Git Error] {e.output}"
        except Exception as e:
            return f"[Git Error] {str(e)}"
    
    # ------------------------------------------------------------------------
    # MCP TOOLS
    # ------------------------------------------------------------------------
    
    def mcp_call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Call a tool on an MCP server. 
        MCP servers must be configured first. Common servers:
        - filesystem: File operations
        - github: GitHub API access
        - postgres: PostgreSQL database access
        - slack: Slack messaging
        """
        if not MCP_AVAILABLE:
            return "[Error] MCP not available. Install with: pip install mcp anthropic-mcp-client"
        
        try:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                self.mcp_manager.call_tool(server_name, tool_name, arguments)
            )
            return result
        except Exception as e:
            return f"[MCP Error] {str(e)}"
    
    def mcp_list_tools(self, server_name: str) -> str:
        """
        List all available tools from an MCP server.
        Use this to discover what tools are available.
        """
        if not MCP_AVAILABLE:
            return "[Error] MCP not available. Install with: pip install mcp anthropic-mcp-client"
        
        try:
            loop = asyncio.get_event_loop()
            tools = loop.run_until_complete(
                self.mcp_manager.list_tools(server_name)
            )
            return format_json(tools)
        except Exception as e:
            return f"[MCP Error] {str(e)}"
    
    # ------------------------------------------------------------------------
    # TIME & DATE TOOLS
    # ------------------------------------------------------------------------
    
    def get_current_time(self, timezone: str = "UTC") -> str:
        """
        Get current date and time in specified timezone.
        Examples: UTC, America/New_York, Europe/London, Asia/Tokyo
        """
        try:
            import pytz
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
            return now.strftime("%Y-%m-%d %H:%M:%S %Z")
        except ImportError:
            # Fallback if pytz not available
            now = datetime.now()
            return now.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            return f"[Error] {str(e)}"
    
    def calculate_time_delta(self, start_time: str, end_time: str = None) -> str:
        """
        Calculate time difference between two dates.
        Format: YYYY-MM-DD HH:MM:SS or YYYY-MM-DD
        If end_time not provided, uses current time.
        """
        try:
            formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]
            
            start = None
            for fmt in formats:
                try:
                    start = datetime.strptime(start_time, fmt)
                    break
                except:
                    continue
            
            if not start:
                return "[Error] Invalid start_time format"
            
            if end_time:
                end = None
                for fmt in formats:
                    try:
                        end = datetime.strptime(end_time, fmt)
                        break
                    except:
                        continue
                if not end:
                    return "[Error] Invalid end_time format"
            else:
                end = datetime.now()
            
            delta = end - start
            
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            return f"{days} days, {hours} hours, {minutes} minutes, {seconds} seconds"
            
        except Exception as e:
            return f"[Error] {str(e)}"
    
    # ------------------------------------------------------------------------
    # TEXT PROCESSING TOOLS
    # ------------------------------------------------------------------------
    
    def count_tokens(self, text: str, model: str = "gpt-3.5-turbo") -> str:
        """
        Estimate token count for text using tiktoken.
        Useful for managing context windows.
        """
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model(model)
            tokens = len(encoding.encode(text))
            return f"Token count: {tokens}\nCharacter count: {len(text)}\nWord count: {len(text.split())}"
        except ImportError:
            # Rough estimate if tiktoken not available
            tokens = len(text) // 4
            return f"Estimated tokens: ~{tokens}\nCharacter count: {len(text)}\nWord count: {len(text.split())}"
        except Exception as e:
            return f"[Error] {str(e)}"
    
    def regex_search(self, pattern: str, text: str, flags: str = "") -> str:
        """
        Search text using regular expressions.
        Flags: i (ignore case), m (multiline), s (dotall)
        """
        try:
            flag_map = {'i': re.IGNORECASE, 'm': re.MULTILINE, 's': re.DOTALL}
            regex_flags = 0
            for f in flags.lower():
                if f in flag_map:
                    regex_flags |= flag_map[f]
            
            matches = re.findall(pattern, text, regex_flags)
            
            if not matches:
                return "No matches found"
            
            result = {
                "pattern": pattern,
                "match_count": len(matches),
                "matches": matches[:100]  # Limit to 100 matches
            }
            return format_json(result)
            
        except Exception as e:
            return f"[Regex Error] {str(e)}"
    
    def text_statistics(self, text: str) -> str:
        """
        Generate comprehensive statistics about text.
        Includes word count, character count, sentence count, etc.
        """
        try:
            lines = text.split('\n')
            words = text.split()
            sentences = re.split(r'[.!?]+', text)
            
            stats = {
                "characters": len(text),
                "characters_no_spaces": len(text.replace(' ', '')),
                "words": len(words),
                "lines": len(lines),
                "sentences": len([s for s in sentences if s.strip()]),
                "paragraphs": len([p for p in text.split('\n\n') if p.strip()]),
                "avg_word_length": sum(len(w) for w in words) / len(words) if words else 0,
                "unique_words": len(set(words))
            }
            
            return format_json(stats)
            
        except Exception as e:
            return f"[Error] {str(e)}"
    
    # ------------------------------------------------------------------------
    # DATA PROCESSING TOOLS
    # ------------------------------------------------------------------------
    
    def parse_json(self, json_string: str) -> str:
        """
        Parse and validate JSON, returning formatted output.
        Useful for debugging and validating JSON data.
        """
        try:
            data = json.loads(json_string)
            return format_json(data)
        except json.JSONDecodeError as e:
            return f"[JSON Error] {str(e)}"
    
    def convert_csv_to_json(self, csv_path: str) -> str:
        """
        Convert CSV file to JSON format.
        """
        try:
            import csv
            csv_path = sanitize_path(csv_path)
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                data = list(reader)
            
            return format_json(data)
            
        except Exception as e:
            return f"[Error] {str(e)}"
    
    def hash_text(self, text: str, algorithm: str = "sha256") -> str:
        """
        Generate cryptographic hash of text.
        Algorithms: md5, sha1, sha256, sha512
        """
        try:
            import hashlib
            
            hash_func = getattr(hashlib, algorithm.lower(), None)
            if not hash_func:
                return f"[Error] Unsupported algorithm: {algorithm}"
            
            hash_obj = hash_func(text.encode('utf-8'))
            
            return f"{algorithm.upper()}: {hash_obj.hexdigest()}"
            
        except Exception as e:
            return f"[Error] {str(e)}"
    
    # ------------------------------------------------------------------------
    # SYSTEM INTROSPECTION TOOLS
    # ------------------------------------------------------------------------
    
    def list_python_modules(self, _: str = "") -> str:
        """List all currently loaded Python modules."""
        modules = sorted(sys.modules.keys())
        return "\n".join(modules)
    
    def get_system_info(self, _: str = "") -> str:
        """
        Get system information including OS, Python version, etc.
        """
        try:
            import platform
            
            info = {
                "os": platform.system(),
                "os_version": platform.release(),
                "architecture": platform.machine(),
                "python_version": sys.version,
                "python_executable": sys.executable,
                "cwd": os.getcwd(),
                "user": os.environ.get('USER', 'unknown')
            }
            
            return format_json(info)
            
        except Exception as e:
            return f"[Error] {str(e)}"
    
    def search_memory(self, query: str, k: int = 5) -> str:
        """
        Search agent's long-term memory for relevant information.
        Uses vector similarity to find related past interactions.
        """
        try:
            docs = self.agent.vectorstore.similarity_search(query, k=k)
            if not docs:
                return "No relevant memories found."
            
            results = [f"--- Memory {i+1} ---\n{doc.page_content}" 
                      for i, doc in enumerate(docs)]
            return "\n\n".join(results)
        except Exception as e:
            return f"[Memory Search Error] {str(e)}"
    
    # ------------------------------------------------------------------------
    # ENVIRONMENT & CONFIGURATION TOOLS
    # ------------------------------------------------------------------------
    
    def get_env_variable(self, var_name: str) -> str:
        """
        Get environment variable value.
        """
        value = os.environ.get(var_name)
        if value is None:
            return f"[Error] Environment variable '{var_name}' not found"
        return value
    
    def list_env_variables(self, _: str = "") -> str:
        """
        List all environment variables (sanitized for security).
        """
        # Filter out sensitive variables
        sensitive_keys = ['password', 'secret', 'key', 'token', 'api']
        
        env_vars = {}
        for key, value in os.environ.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                env_vars[key] = "[HIDDEN]"
            else:
                env_vars[key] = value
        
        return format_json(env_vars)

"""
Integration of Babelfish and WebServer tools into the existing tools.py framework
Add this section to your tools.py file
"""

from typing import Literal, Union
import threading

# ============================================================================
# BABELFISH TOOLS CLASS
# ============================================================================
from Vera.Toolchain.Tools.Babelfish.babelfish import BabelFishTool, WebServerTool

class BabelfishTools:
    """Wrapper for Babelfish multi-protocol communication tools."""
    
    def __init__(self, agent):
        self.agent = agent
        
        # Import Babelfish components (lazy to avoid import errors)
        try:
            self.babelfish = BabelFishTool()
            self.webserver = WebServerTool()
            self.available = True
        except ImportError:
            self.babelfish = None
            self.webserver = None
            self.available = False
            print("[Warning] Babelfish module not available")
    
    def protocol_communicate(self, protocol: str, action: str, params: Dict[str, Any]) -> str:
        """
        Universal protocol communication via Babelfish.
        
        Supported protocols:
        - http: HTTP/HTTPS requests
        - ws: WebSocket connections (persistent)
        - mqtt: MQTT pub/sub messaging
        - tcp: Raw TCP sockets (client/server)
        - udp: UDP datagrams (client/server)
        - smtp: Email sending via SMTP
        
        Common actions by protocol:
        
        HTTP:
        - action: "request" (implied)
        - params: {method: "GET|POST|PUT|DELETE", url: str, headers: dict, 
                  data: str, json: dict, timeout: int, verify: bool}
        
        WebSocket:
        - action: "open" -> returns handle
        - params: {url: str, headers: dict, subprotocols: list}
        - action: "send" -> params: {url: str, message: str}
        
        MQTT:
        - action: "connect" -> returns handle
        - params: {host: str, port: int, username: str, password: str, 
                  subscribe: [topics], tls: dict}
        - action: "publish" -> params: {handle: str, topic: str, payload: str, qos: int}
        - action: "subscribe" -> params: {handle: str, topics: list}
        - action: "disconnect" -> params: {handle: str}
        
        TCP:
        - action: "send" -> params: {host: str, port: int, data: str, data_b64: str}
        - action: "listen" -> returns handle, params: {host: str, port: int}
        - action: "close" -> params: {handle: str}
        
        UDP:
        - action: "send" -> params: {host: str, port: int, data: str, expect_response: bool}
        - action: "listen" -> returns handle, params: {host: str, port: int}
        - action: "close" -> params: {handle: str}
        
        SMTP:
        - action: "send" -> params: {host: str, port: int, from_addr: str, 
                  to_addrs: list, message: str, username: str, password: str, tls: bool}
        
        Returns JSON result: {"ok": bool, "data": any, "error": str}
        """
        if not self.available:
            return json.dumps({"ok": False, "error": "Babelfish not available"})
        
        try:
            query = {
                "protocol": protocol,
                "action": action,
                "params": params
            }
            
            result = self.babelfish._run(query)
            
            # Store in agent memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                f"{protocol}:{action}",
                "babelfish_action",
                metadata={
                    "protocol": protocol,
                    "action": action,
                    "params_keys": list(params.keys())
                }
            )
            
            return result
            
        except Exception as e:
            return json.dumps({
                "ok": False,
                "error": f"Babelfish error: {str(e)}"
            })
    
    def handle_operations(self, action: str, params: Dict[str, Any]) -> str:
        """
        Manage Babelfish connection handles.
        
        Actions:
        - handles/list: List active handles
          params: {kind: "ws|mqtt|tcp|udp"} (optional filter)
        
        - handles/read: Read queued messages from a handle
          params: {handle: str, max_items: int}
          Returns messages that arrived on persistent connections
        
        - handles/close: Close a handle and clean up
          params: {handle: str}
        
        Handles are used for persistent connections (WebSocket, MQTT, TCP/UDP listeners).
        After opening such a connection, use the returned handle ID to read messages
        or perform additional operations.
        """
        if not self.available:
            return json.dumps({"ok": False, "error": "Babelfish not available"})
        
        try:
            query = {
                "action": action,
                "params": params
            }
            
            result = self.babelfish._run(query)
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                action,
                "babelfish_handle_op",
                metadata={"action": action}
            )
            
            return result
            
        except Exception as e:
            return json.dumps({
                "ok": False,
                "error": f"Handle operation error: {str(e)}"
            })
    
    def webserver_control(self, action: str, params: Dict[str, Any]) -> str:
        """
        Control a dynamic FastAPI web server.
        
        Actions:
        
        - start: Start the web server
          params: {host: "0.0.0.0", port: 8000, log_level: "info"}
          Returns: {status: "started", url: "http://host:port"}
        
        - add_static: Mount a static file directory
          params: {route: "/static", folder: "/path/to/folder"}
          Serves files from folder at the specified route
        
        - add_dynamic: Create a dynamic endpoint
          params: {
              route: "/api/endpoint",
              method: "GET|POST|PUT|DELETE",
              handler: {
                  type: "json|text|file|python",
                  
                  # For type="json":
                  body: {json: "response"}
                  
                  # For type="text":
                  text: "response text"
                  
                  # For type="file":
                  path: "/path/to/file"
                  
                  # For type="python":
                  code: "return {'dynamic': 'response'}"
              }
          }
        
        - remove_route: Remove a route (marks as removed, FastAPI limitation)
          params: {route: "/api/endpoint"}
        
        - list_routes: List all registered routes
          params: {}
        
        Use this to create temporary APIs, serve files, or test endpoints.
        The server runs in a background thread.
        """
        if not self.available:
            return json.dumps({"ok": False, "error": "WebServer not available"})
        
        try:
            query = {
                "action": action,
                "params": params
            }
            
            result = self.webserver._run(query)
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                action,
                "webserver_action",
                metadata={
                    "action": action,
                    "route": params.get("route", "")
                }
            )
            
            return result
            
        except Exception as e:
            return json.dumps({
                "ok": False,
                "error": f"WebServer error: {str(e)}"
            })


# ============================================================================
# ADVANCED BABELFISH INTEGRATION (HTTP/3, WebRTC)
# ============================================================================
from Vera.Toolchain.Tools.Babelfish.babelfish import Babelfish

class AdvancedBabelfishTools:
    """
    Advanced Babelfish carriers: HTTP/3 (QUIC) and WebRTC.
    Requires: pip install aioquic aiortc
    """
    
    def __init__(self, agent):
        self.agent = agent
        
        try:
            self.bf = Babelfish()
            self.available = True
        except ImportError:
            self.bf = None
            self.available = False
            print("[Warning] Advanced Babelfish (QUIC/WebRTC) not available")
    
    def quic_http3_request(self, url: str, method: str = "GET", 
                          headers: Optional[Dict[str, str]] = None,
                          body: Optional[str] = None) -> str:
        """
        Make HTTP/3 request over QUIC.
        
        HTTP/3 provides:
        - Faster connection establishment (0-RTT)
        - Better multiplexing than HTTP/2
        - Improved loss recovery
        - Better mobile performance
        
        Args:
            url: Target URL (must be https://)
            method: HTTP method (GET, POST, PUT, DELETE)
            headers: Optional HTTP headers
            body: Optional request body
        
        Returns JSON with received headers and data.
        """
        if not self.available:
            return json.dumps({"ok": False, "error": "HTTP/3 not available"})
        
        try:
            params = {
                "url": url,
                "method": method,
                "headers": headers or {},
            }
            if body:
                params["body"] = body
            
            handle_id = self.bf.open("http3", params)
            
            # Read response
            import time
            time.sleep(0.5)  # Allow time for response
            messages = self.bf.receive(handle_id, max_items=100)
            
            self.bf.close(handle_id)
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                url,
                "http3_request",
                metadata={"method": method, "url": url}
            )
            
            return json.dumps({
                "ok": True,
                "data": {
                    "handle": handle_id,
                    "messages": messages
                }
            })
            
        except Exception as e:
            return json.dumps({
                "ok": False,
                "error": f"HTTP/3 error: {str(e)}"
            })
    
    def webrtc_connect(self, role: str = "offer",
                      stun: Optional[str] = None,
                      turn: Optional[str] = None,
                      turn_username: Optional[str] = None,
                      turn_password: Optional[str] = None,
                      label: str = "datachannel") -> str:
        """
        Establish WebRTC DataChannel connection.
        
        WebRTC provides:
        - Peer-to-peer communication
        - NAT traversal via STUN/TURN
        - Encrypted data channels
        - Low latency real-time communication
        
        Args:
            role: "offer" (initiator) or "answer" (responder)
            stun: STUN server URL (e.g., "stun:stun.l.google.com:19302")
            turn: TURN server URL for NAT traversal
            turn_username: TURN authentication username
            turn_password: TURN authentication password
            label: DataChannel label
        
        Note: Requires signaling mechanism (WebSocket, HTTP, etc.)
        You must implement send_signal and wait_signal callbacks.
        
        Returns handle ID for sending/receiving data.
        """
        if not self.available:
            return json.dumps({"ok": False, "error": "WebRTC not available"})
        
        try:
            # This is a scaffold - you need to provide signaling
            return json.dumps({
                "ok": False,
                "error": "WebRTC requires custom signaling implementation. See documentation.",
                "hint": "Provide send_signal and wait_signal callbacks in params"
            })
            
        except Exception as e:
            return json.dumps({
                "ok": False,
                "error": f"WebRTC error: {str(e)}"
            })


# ============================================================================
# ADD TO TOOLLOADER FUNCTION
# ============================================================================

def add_babelfish_tools(tool_list: List, agent):
    """
    Add Babelfish multi-protocol communication tools.
    Call this in your ToolLoader function:
    
    tool_list = ToolLoader(agent)
    add_babelfish_tools(tool_list, agent)
    return tool_list
    """
    
    bf_tools = BabelfishTools(agent)
    
    if not bf_tools.available:
        print("[Info] Babelfish tools not loaded - module not available")
        return tool_list
    
    # Main Babelfish protocol tool
    tool_list.append(
        StructuredTool.from_function(
            func=bf_tools.protocol_communicate,
            name="babelfish",
            description=(
                "Universal multi-protocol communication tool. "
                "Supports HTTP/HTTPS, WebSocket, MQTT, TCP, UDP, SMTP. "
                "Enables persistent connections with handles, pub/sub messaging, "
                "socket servers, email sending, and more. "
                "Returns JSON: {ok: bool, data: any, error: str}"
            ),
            args_schema=BabelfishProtocolInput
        )
    )
    
    # Handle management tool
    tool_list.append(
        StructuredTool.from_function(
            func=bf_tools.handle_operations,
            name="babelfish_handles",
            description=(
                "Manage Babelfish connection handles. "
                "List active connections, read queued messages from persistent connections "
                "(WebSocket, MQTT, TCP/UDP listeners), or close handles. "
                "Essential for working with bidirectional protocols."
            ),
            args_schema=BabelfishHandleInput
        )
    )
    
    # WebServer tool
    tool_list.append(
        StructuredTool.from_function(
            func=bf_tools.webserver_control,
            name="webserver",
            description=(
                "Control a dynamic FastAPI web server. "
                "Start server, mount static directories, create dynamic endpoints "
                "(JSON, text, file, Python handlers), remove routes, list routes. "
                "Useful for creating temporary APIs, serving files, or testing. "
                "Server runs in background thread."
            ),
            args_schema=WebServerInput
        )
    )
    
    # Advanced tools (HTTP/3, WebRTC)
    adv_tools = AdvancedBabelfishTools(agent)
    
    if adv_tools.available:
        tool_list.extend([
            StructuredTool.from_function(
                func=adv_tools.quic_http3_request,
                name="http3_request",
                description=(
                    "Make HTTP/3 request over QUIC protocol. "
                    "Faster than HTTP/2, better multiplexing, 0-RTT connection. "
                    "Ideal for modern APIs and mobile networks."
                ),
                args_schema=HTTPInput
            ),
            StructuredTool.from_function(
                func=adv_tools.webrtc_connect,
                name="webrtc_connect",
                description=(
                    "Establish WebRTC DataChannel for peer-to-peer communication. "
                    "Supports STUN/TURN for NAT traversal, encrypted channels, "
                    "low-latency real-time data transfer. Requires signaling setup."
                ),
                args_schema=SearchInput  # Reuse for basic params
            ),
        ])
    
    return tool_list

# Required dependencies for Babelfish (add to requirements.txt):
# fastapi>=0.104.0
# uvicorn>=0.24.0
# websockets>=12.0
# paho-mqtt>=1.6.1
# requests>=2.31.0
# # Optional for advanced features:
# aioquic>=0.9.21
# aiortc>=1.6.0
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


# ============================================================================
# ADD TO TOOLLOADER FUNCTION
# ============================================================================

def add_web_crawler_tools(tool_list: List, agent):
    """
    Add web crawler tools to the tool list.
    
    Provides:
    - Web crawling with technology detection
    - Semantic search over crawled content
    - Intelligent web navigation
    - Common Crawl fallback for blocked sites
    
    Call this in ToolLoader:
        tool_list = ToolLoader(agent)
        add_web_crawler_tools(tool_list, agent)
        return tool_list
    """
    
    web_tools = WebCrawlerTools(agent)
    
    if not web_tools.available:
        print("[Info] Web Crawler tools not loaded - module not available")
        return tool_list
    
    tool_list.extend([
        StructuredTool.from_function(
            func=web_tools.crawl_website,
            name="crawl_website",
            description=(
                "Crawl website and store content in searchable memory. "
                "Detects technologies, generates AI summaries, saves HTML. "
                "Falls back to Common Crawl archives if blocked. "
                "Use for deep web research, documentation mining, tech stack analysis."
            ),
            args_schema=WebCrawlInput
        ),
        
        StructuredTool.from_function(
            func=web_tools.query_crawl_memory,
            name="query_crawl_memory",
            description=(
                "Search previously crawled website content using semantic similarity. "
                "Returns relevant pages with summaries and URLs. "
                "Perfect for finding specific documentation, answering questions "
                "about crawled sites, or discovering related content."
            ),
            args_schema=WebMemoryQueryInput
        ),
        
        StructuredTool.from_function(
            func=web_tools.navigate_web_intelligent,
            name="navigate_web_smart",
            description=(
                "AI-powered web navigation and research assistant. "
                "Understands natural language instructions, auto-crawls if needed, "
                "synthesizes information from multiple pages. "
                "Use for complex web research tasks and intelligent content discovery."
            ),
            args_schema=WebNavigateInput
        ),
        
        StructuredTool.from_function(
            func=web_tools.detect_technologies,
            name="detect_web_technologies",
            description=(
                "Detect technologies used on a website. "
                "Identifies frameworks, libraries, analytics, CMS systems. "
                "Analyzes HTML, scripts, and resources for technology fingerprints."
            ),
            args_schema=WebTechDetectInput
        ),
        
        StructuredTool.from_function(
            func=web_tools.list_crawled_sites,
            name="list_crawled_sites",
            description=(
                "List recently crawled websites with metadata. "
                "Shows URLs, technologies detected, crawl depth, and timestamps."
            ),
            args_schema=SearchInput  # Reuse existing schema
        ),
    ])
    
    return tool_list



# Required dependencies for Web Crawler (add to requirements.txt):
# beautifulsoup4>=4.12.0
# chromadb>=0.4.0
# sentence-transformers>=2.2.0
# warcio>=1.7.4
# langchain>=0.1.0
# langchain-community>=0.0.1

# ============================================================================
# TOOL LOADER - Creates LangChain Tool instances
# ============================================================================

def ToolLoader(agent):
    """
    Create and return a list of LangChain Tool instances with proper schemas.
    
    Args:
        agent: Agent instance with mem, sess, fast_llm, deep_llm, vectorstore
    
    Returns:
        List[Tool]: Configured tools ready for LangChain agent use
    """
    tools = LLMTools(agent)
    
    tool_list = [
        # LLM Interaction Tools
        StructuredTool.from_function(
            func=tools.fast_llm_query,
            name="fast_llm",
            description="Query fast LLM for quick tasks: creative writing, text review, summarization. Fast but less accurate.",
            args_schema=LLMQueryInput
        ),
        StructuredTool.from_function(
            func=tools.deep_llm_query,
            name="deep_llm",
            description="Query deep LLM for complex reasoning and detailed analysis. Slower but more accurate.",
            args_schema=LLMQueryInput
        ),
        
        # File System Tools
        StructuredTool.from_function(
            func=tools.read_file,
            name="read_file",
            description="Read contents of a text file. Provide full file path.",
            args_schema=FilePathInput
        ),
        StructuredTool.from_function(
            func=tools.write_file,
            name="write_file",
            description="Write content to a file. Creates directories if needed. Overwrites existing files.",
            args_schema=WriteFileInput
        ),
        StructuredTool.from_function(
            func=tools.list_directory,
            name="list_directory",
            description="List directory contents with file sizes and types.",
            args_schema=FilePathInput
        ),
        StructuredTool.from_function(
            func=tools.search_files,
            name="search_files",
            description="Search for files matching a pattern recursively. Supports glob and regex patterns.",
            args_schema=SearchInput
        ),
        
        # Code Execution Tools
        StructuredTool.from_function(
            func=tools.run_python,
            name="python",
            description="Execute Python code. Use print() for output. Supports both expressions and statements.",
            args_schema=PythonInput
        ),
        StructuredTool.from_function(
            func=tools.run_bash_command,
            name="bash",
            description="Execute bash command. Returns command output. Use with caution.",
            args_schema=CommandInput
        ),
        
        # Web Search Tools
        StructuredTool.from_function(
            func=tools.search_web,
            name="web_search",
            description="Advanced web search using Playwright for robustness.Supports multiple search engines with automatic fallback.",
            args_schema=SearchInput
        ),
        StructuredTool.from_function(
            func=tools.search_news,
            name="news_search",
            description="Search recent news using DuckDuckGo News. Best for current events.",
            args_schema=SearchInput
        ),
        StructuredTool.from_function(
            func=tools.web_search_deep,
            name="web_search_deep",
            description="Comprehensive web search with full page scraping. Use for in-depth information.",
            args_schema=WebReportInput
        ),
        
        # HTTP/API Tools
        StructuredTool.from_function(
            func=tools.http_request,
            name="http_request",
            description="Make HTTP requests to APIs. Supports GET, POST, PUT, DELETE methods.",
            args_schema=HTTPInput
        ),
        
        # Database Tools
        StructuredTool.from_function(
            func=tools.sqlite_query,
            name="sqlite_query",
            description="Execute SQLite queries. Supports SELECT, INSERT, UPDATE, DELETE.",
            args_schema=SQLInput
        ),
        
        # Git Tools
        StructuredTool.from_function(
            func=tools.git_operation,
            name="git",
            description="Execute git commands: status, log, diff, branch, add, commit, push, pull.",
            args_schema=GitInput
        ),
        
        # Time & Date Tools
        StructuredTool.from_function(
            func=tools.get_current_time,
            name="get_time",
            description="Get current date and time in specified timezone.",
            args_schema=LLMQueryInput
        ),
        StructuredTool.from_function(
            func=tools.calculate_time_delta,
            name="time_delta",
            description="Calculate time difference between two dates or from date to now.",
            args_schema=SearchInput
        ),
        
        # Text Processing Tools
        StructuredTool.from_function(
            func=tools.count_tokens,
            name="count_tokens",
            description="Estimate token count for text. Useful for managing context windows.",
            args_schema=SearchInput
        ),
        StructuredTool.from_function(
            func=tools.regex_search,
            name="regex_search",
            description="Search text using regular expressions with optional flags.",
            args_schema=SearchInput
        ),
        StructuredTool.from_function(
            func=tools.text_statistics,
            name="text_stats",
            description="Generate comprehensive statistics about text (word count, sentences, etc).",
            args_schema=LLMQueryInput
        ),
        
        # Data Processing Tools
        StructuredTool.from_function(
            func=tools.parse_json,
            name="parse_json",
            description="Parse and validate JSON, returning formatted output.",
            args_schema=LLMQueryInput
        ),
        StructuredTool.from_function(
            func=tools.convert_csv_to_json,
            name="csv_to_json",
            description="Convert CSV file to JSON format.",
            args_schema=FilePathInput
        ),
        StructuredTool.from_function(
            func=tools.hash_text,
            name="hash_text",
            description="Generate cryptographic hash (md5, sha1, sha256, sha512) of text.",
            args_schema=SearchInput
        ),
        
        # System Tools
        StructuredTool.from_function(
            func=tools.get_system_info,
            name="system_info",
            description="Get system information including OS, Python version, etc.",
        ),
        StructuredTool.from_function(
            func=tools.get_env_variable,
            name="get_env",
            description="Get environment variable value.",
            args_schema=LLMQueryInput
        ),
        StructuredTool.from_function(
            func=tools.list_env_variables,
            name="list_env",
            description="List all environment variables (sanitized).",
        ),
        
        # Memory & Search Tools
        StructuredTool.from_function(
            func=tools.search_memory,
            name="search_memory",
            description="Search agent's long-term memory for relevant past information.",
            args_schema=LLMQueryInput
        ),
        StructuredTool.from_function(
            func=tools.list_python_modules,
            name="list_modules",
            description="List all currently loaded Python modules in the runtime.",
        ),
    ]
    
    DynamicTools.add_dynamic_tools(tool_list, agent)

    add_ssh_postgres_neo4j_tools(tool_list, agent)

    add_mcp_docker_tools(tool_list, agent)
    
    add_adhoc_code_tools(tool_list, agent)

    add_microcontroller_control_tools(tool_list, agent)

    add_versioned_file_tools(tool_list, agent)

    add_n8n_tools(tool_list, agent)

    # Add Web Crawler tools
    # add_web_crawler_tools(tool_list, agent)
    # ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    # ERROR:Vera.ChatUI.api.session:Session start error: "CrawlWebsiteTool" object has no field "config"
    # Traceback (most recent call last):
    # File "/home/boejaker/langchain/app/Vera/ChatUI/api/session.py", line 93, in start_session
    #     vera = await loop.run_in_executor(executor, create_vera)
    #         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    # File "/usr/lib/python3.11/concurrent/futures/thread.py", line 58, in run
    #     result = self.fn(*self.args, **self.kwargs)
    #             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    # File "/home/boejaker/langchain/app/Vera/ChatUI/api/session.py", line 89, in create_vera
    #     return Vera()
    #         ^^^^^^
    # File "/home/boejaker/langchain/app/Vera/vera.py", line 589, in __init__
    #     self.toolkit=ToolLoader(self)
    #                 ^^^^^^^^^^^^^^^^
    # File "/home/boejaker/langchain/app/Vera/Toolchain/tools.py", line 2414, in ToolLoader
    #     add_web_crawler_tools(tool_list, agent)
    # File "/home/boejaker/langchain/app/Vera/Toolchain/tools.py", line 2121, in add_web_crawler_tools
    #     web_tools = WebCrawlerTools(agent)
    #                 ^^^^^^^^^^^^^^^^^^^^^^
    # File "/home/boejaker/langchain/app/Vera/Toolchain/tools.py", line 1772, in __init__
    #     self.toolkit = WebCrawlerToolkit(self.config)
    #                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    # File "/home/boejaker/langchain/app/Vera/Toolchain/Tools/Crawlers/corpus_crawler.py", line 589, in __init__
    #     self.crawl_tool = CrawlWebsiteTool(self.config)
    #                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    # File "/home/boejaker/langchain/app/Vera/Toolchain/Tools/Crawlers/corpus_crawler.py", line 437, in __init__
    #     self.config = config
    #     ^^^^^^^^^^^
    # File "/home/boejaker/langchain/lib/python3.11/site-packages/pydantic/main.py", line 997, in __setattr__
    #     elif (setattr_handler := self._setattr_handler(name, value)) is not None:
    #                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    # File "/home/boejaker/langchain/lib/python3.11/site-packages/pydantic/main.py", line 1044, in _setattr_handler
    #     raise ValueError(f'"{cls.__name__}" object has no field "{name}"')
    # ValueError: "CrawlWebsiteTool" object has no field "config"


    # Add Babelfish tools
    add_babelfish_tools(tool_list, agent)

    add_orchestrator_tools(tool_list, agent)
    tool_list.extend(add_memory_tools(agent))
    add_advanced_memory_search_tools(tool_list, agent)
    add_extended_memory_search_tools(tool_list, agent)
    add_all_osint_tools(tool_list, agent)


    # Add MCP tools if available
    if MCP_AVAILABLE:
        tool_list.extend([
            StructuredTool.from_function(
                func=tools.mcp_call_tool,
                name="mcp_call",
                description="Call a tool on an MCP server (filesystem, github, postgres, slack, etc).",
                args_schema=MCPInput
            ),
            StructuredTool.from_function(
                func=tools.mcp_list_tools,
                name="mcp_list_tools",
                description="List all available tools from an MCP server.",
                args_schema=LLMQueryInput
            ),
        ])
    
    # Add executive assistant if available
    if hasattr(agent, 'executive_instance') and agent.executive_instance:
        tool_list.append(
            StructuredTool.from_function(
                func=agent.executive_instance.main,
                name="scheduling_assistant",
                description="Run the executive scheduling assistant. Access to calendars, todos, scheduling apps. Input: query string.",
            )
        )
    
    return tool_list

    
# # ============================================================================
# # EXAMPLE CUSTOM TOOL FILE (save as custom_tools/example_tool.py)
# # ============================================================================

# EXAMPLE_TOOL_TEMPLATE = '''"""
# Example custom tool - save this as: custom_tools/example_tool.py

# Functions decorated with @tool will be automatically loaded.
# Functions without decorator can be called via call_custom_tool.
# """

# from tools import tool
# from typing import Optional

# @tool(
#     name="greet_user",
#     description="Greet a user with a personalized message",
#     category="examples"
# )
# def greet_user(agent, name: str, greeting: str = "Hello") -> str:
#     """
#     Greet a user by name with a custom greeting.
    
#     Args:
#         agent: Agent instance (auto-injected)
#         name: User\'s name
#         greeting: Greeting word (default: "Hello")
    
#     Returns:
#         Personalized greeting message
#     """
#     return f"{greeting}, {name}! Nice to meet you."


# @tool(
#     name="calculate_stats",
#     description="Calculate basic statistics for a list of numbers",
#     category="examples"
# )
# def calculate_stats(agent, numbers: str) -> str:
#     """
#     Calculate mean, median, and sum for comma-separated numbers.
    
#     Args:
#         agent: Agent instance (auto-injected)
#         numbers: Comma-separated numbers (e.g., "1,2,3,4,5")
    
#     Returns:
#         Statistics as formatted string
#     """
#     try:
#         nums = [float(x.strip()) for x in numbers.split(",")]
        
#         mean = sum(nums) / len(nums)
#         sorted_nums = sorted(nums)
#         median = sorted_nums[len(sorted_nums) // 2]
        
#         return f"Count: {len(nums)}\\nSum: {sum(nums)}\\nMean: {mean:.2f}\\nMedian: {median}"
#     except Exception as e:
#         return f"Error: {str(e)}"


# # Function without decorator - callable via call_custom_tool
# def process_text(text: str, operation: str = "upper") -> str:
#     """
#     Process text with various operations.
    
#     Args:
#         text: Input text
#         operation: Operation to perform (upper, lower, reverse, length)
    
#     Returns:
#         Processed text
#     """
#     operations = {
#         "upper": lambda t: t.upper(),
#         "lower": lambda t: t.lower(),
#         "reverse": lambda t: t[::-1],
#         "length": lambda t: f"Length: {len(t)}"
#     }
    
#     if operation not in operations:
#         return f"Unknown operation. Available: {', '.join(operations.keys())}"
    
#     return operations[operation](text)
# '''


# def create_example_tool_file(tools_directory: str = "./custom_tools"):
#     """
#     Create an example tool file to demonstrate the system.
#     """
#     tools_dir = Path(tools_directory)
#     tools_dir.mkdir(exist_ok=True)
    
#     example_file = tools_dir / "example_tool.py"
    
#     if not example_file.exists():
#         example_file.write_text(EXAMPLE_TOOL_TEMPLATE)
#         print(f"✓ Created example tool file: {example_file}")
#         return str(example_file)
#     else:
#         print(f"ℹ Example tool file already exists: {example_file}")
#         return str(example_file)