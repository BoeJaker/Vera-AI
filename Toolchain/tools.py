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


# ============================================================================
# INPUT SCHEMAS - Strongly typed inputs for better LLM understanding
# ============================================================================

class FilePathInput(BaseModel):
    """Input schema for file path operations."""
    path: str = Field(..., description="Full path to the file")


class WriteFileInput(BaseModel):
    """Input schema for writing files."""
    path: str = Field(..., description="Full path where file should be written")
    content: str = Field(..., description="Content to write to the file")


class CommandInput(BaseModel):
    """Input schema for shell commands."""
    command: str = Field(..., description="Shell command to execute")


class PythonInput(BaseModel):
    """Input schema for Python code execution."""
    code: str = Field(..., description="Python code to execute")


class SearchInput(BaseModel):
    """Input schema for web searches."""
    query: str = Field(..., description="Search query")
    max_results: int = Field(default=10, description="Maximum number of results to return")
    search_engine: str = Field(default="duckduckgo", description="Search engine to use: duckduckgo, google, bing, brave, perplexity")


class WebReportInput(BaseModel):
    """Input schema for comprehensive web search reports."""
    input_data: str = Field(..., description="Search query or existing search results text")
    max_results: int = Field(default=5, description="Maximum number of pages to scrape")


class LLMQueryInput(BaseModel):
    """Input schema for LLM queries."""
    query: str = Field(..., description="Query or prompt for the LLM")


class MCPInput(BaseModel):
    """Input schema for MCP operations."""
    server_name: str = Field(..., description="Name of the MCP server to use")
    tool_name: str = Field(..., description="Name of the tool to invoke")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool")


class HTTPInput(BaseModel):
    """Input schema for HTTP requests."""
    url: str = Field(..., description="URL to request")
    method: str = Field(default="GET", description="HTTP method (GET, POST, PUT, DELETE)")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Request headers")
    body: Optional[str] = Field(default=None, description="Request body for POST/PUT")


class SQLInput(BaseModel):
    """Input schema for SQLite operations."""
    db_path: str = Field(..., description="Path to SQLite database")
    query: str = Field(..., description="SQL query to execute")


class GitInput(BaseModel):
    """Input schema for Git operations."""
    repo_path: str = Field(default=".", description="Path to git repository")
    command: str = Field(..., description="Git command (status, log, diff, etc.)")
    args: str = Field(default="", description="Additional arguments for the command")


class CustomToolInput(BaseModel):
    """Input schema for custom tool operations."""
    tool_name: str = Field(..., description="Name of the tool file (without .py extension)")
    function_name: str = Field(..., description="Name of the function to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to the function as key-value pairs")


class ToolDiscoveryInput(BaseModel):
    """Input schema for tool discovery."""
    pattern: str = Field(default="*", description="Pattern to filter tools (e.g., 'data_*' or '*')")


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
Dynamic Tool Loading System - Add this to your existing tools.py
Enables loading tools from external files and decorating functions for auto-discovery
"""

import importlib.util
import inspect
from pathlib import Path
from typing import Callable, Optional, Any, Dict, List
from functools import wraps
from pydantic import BaseModel, Field, create_model


# ============================================================================
# TOOL DECORATOR & REGISTRY
# ============================================================================

class ToolRegistry:
    """Global registry for decorated tools."""
    _tools: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    def register(cls, name: str, func: Callable, description: str, 
                 schema: Optional[type] = None, category: str = "general"):
        """Register a tool in the global registry."""
        cls._tools[name] = {
            "function": func,
            "description": description,
            "schema": schema,
            "category": category,
            "module": func.__module__
        }
    
    @classmethod
    def get_tool(cls, name: str) -> Optional[Dict[str, Any]]:
        """Get a tool by name."""
        return cls._tools.get(name)
    
    @classmethod
    def list_tools(cls, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all registered tools, optionally filtered by category."""
        if category:
            return [
                {"name": name, **info} 
                for name, info in cls._tools.items() 
                if info["category"] == category
            ]
        return [{"name": name, **info} for name, info in cls._tools.items()]
    
    @classmethod
    def clear(cls):
        """Clear all registered tools."""
        cls._tools.clear()


def tool(name: str = None, description: str = None, 
         schema: type = None, category: str = "general"):
    """
    Decorator to register a function as a tool.
    
    Usage:
        @tool(name="my_tool", description="Does something useful")
        def my_function(agent, param1: str, param2: int = 10):
            return f"Result: {param1} {param2}"
    
    Args:
        name: Tool name (defaults to function name)
        description: Tool description (defaults to docstring)
        schema: Pydantic model for input validation
        category: Tool category for organization
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        tool_desc = description or func.__doc__ or "No description provided"
        
        # Auto-generate schema from function signature if not provided
        if schema is None:
            sig = inspect.signature(func)
            params = {}
            
            # Skip 'agent' parameter which is injected
            for param_name, param in sig.parameters.items():
                if param_name == 'agent':
                    continue
                
                # Get type annotation
                param_type = param.annotation if param.annotation != inspect.Parameter.empty else str
                
                # Get default value
                if param.default != inspect.Parameter.empty:
                    params[param_name] = (param_type, Field(default=param.default))
                else:
                    params[param_name] = (param_type, Field(...))
            
            # Create dynamic Pydantic model
            if params:
                tool_schema = create_model(
                    f"{tool_name.title()}Input",
                    **params
                )
            else:
                tool_schema = None
        else:
            tool_schema = schema
        
        # Register the tool
        ToolRegistry.register(
            name=tool_name,
            func=func,
            description=tool_desc,
            schema=tool_schema,
            category=category
        )
        
        # Add metadata to function
        func._tool_metadata = {
            "name": tool_name,
            "description": tool_desc,
            "schema": tool_schema,
            "category": category
        }
        
        return func
    
    return decorator


# ============================================================================
# DYNAMIC TOOL LOADER
# ============================================================================

class DynamicToolLoader:
    """Loads tools dynamically from Python files in a directory."""
    
    def __init__(self, agent, tools_directory: str = "./tools"):
        self.agent = agent
        self.tools_directory = Path(tools_directory)
        self.loaded_modules = {}
        
        # Create tools directory if it doesn't exist
        self.tools_directory.mkdir(exist_ok=True)
        
        # Create __init__.py if it doesn't exist
        init_file = self.tools_directory / "__init__.py"
        if not init_file.exists():
            init_file.touch()
    
    def discover_tools(self, pattern: str = "*.py") -> List[str]:
        """
        Discover all Python files in the tools directory.
        
        Returns:
            List of tool file names (without .py extension)
        """
        tool_files = []
        
        for file_path in self.tools_directory.glob(pattern):
            if file_path.name.startswith("_"):
                continue  # Skip private files
            
            if file_path.suffix == ".py":
                tool_files.append(file_path.stem)
        
        return sorted(tool_files)
    
    def load_tool_module(self, module_name: str) -> Any:
        """
        Dynamically load a Python module from the tools directory.
        
        Args:
            module_name: Name of the module (without .py)
        
        Returns:
            Loaded module object
        """
        if module_name in self.loaded_modules:
            return self.loaded_modules[module_name]
        
        module_path = self.tools_directory / f"{module_name}.py"
        
        if not module_path.exists():
            raise FileNotFoundError(f"Tool module not found: {module_path}")
        
        # Load the module
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Cache the module
        self.loaded_modules[module_name] = module
        
        return module
    
    def get_tool_function(self, module_name: str, function_name: str) -> Callable:
        """
        Get a specific function from a tool module.
        
        Args:
            module_name: Name of the tool module
            function_name: Name of the function in the module
        
        Returns:
            The function object
        """
        module = self.load_tool_module(module_name)
        
        if not hasattr(module, function_name):
            raise AttributeError(f"Function '{function_name}' not found in module '{module_name}'")
        
        func = getattr(module, function_name)
        
        if not callable(func):
            raise TypeError(f"'{function_name}' in module '{module_name}' is not callable")
        
        return func
    
    def call_tool_function(self, module_name: str, function_name: str, 
                          arguments: Dict[str, Any]) -> str:
        """
        Call a function from a tool module with arguments.
        
        Args:
            module_name: Name of the tool module
            function_name: Name of the function
            arguments: Dictionary of arguments to pass
        
        Returns:
            Function result as string
        """
        try:
            func = self.get_tool_function(module_name, function_name)
            
            # Check if function expects 'agent' parameter
            sig = inspect.signature(func)
            if 'agent' in sig.parameters:
                result = func(self.agent, **arguments)
            else:
                result = func(**arguments)
            
            return str(result)
            
        except Exception as e:
            return f"[Tool Execution Error] {str(e)}\n{traceback.format_exc()}"
    
    def list_tool_functions(self, module_name: str) -> List[Dict[str, Any]]:
        """
        List all functions in a tool module.
        
        Args:
            module_name: Name of the tool module
        
        Returns:
            List of function info dictionaries
        """
        module = self.load_tool_module(module_name)
        
        functions = []
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) and not name.startswith('_'):
                # Get function signature
                sig = inspect.signature(obj)
                params = [
                    {
                        "name": param_name,
                        "type": str(param.annotation) if param.annotation != inspect.Parameter.empty else "Any",
                        "default": str(param.default) if param.default != inspect.Parameter.empty else None
                    }
                    for param_name, param in sig.parameters.items()
                    if param_name != 'agent'  # Skip agent parameter
                ]
                
                functions.append({
                    "name": name,
                    "docstring": obj.__doc__ or "No description",
                    "parameters": params,
                    "has_tool_decorator": hasattr(obj, '_tool_metadata')
                })
        
        return functions
    
    def auto_load_decorated_tools(self, pattern: str = "*.py") -> List[StructuredTool]:
        """
        Automatically load all tools decorated with @tool from the tools directory.
        
        Args:
            pattern: File pattern to search for
        
        Returns:
            List of StructuredTool instances
        """
        tool_files = self.discover_tools(pattern)
        loaded_tools = []
        
        for module_name in tool_files:
            try:
                # Load the module (which will trigger decorator registration)
                self.load_tool_module(module_name)
            except Exception as e:
                print(f"[Warning] Failed to load tool module '{module_name}': {e}")
                continue
        
        # Convert registered tools to StructuredTool instances
        for tool_name, tool_info in ToolRegistry.list_tools():
            try:
                func = tool_info["function"]
                
                # Wrap function to inject agent
                @wraps(func)
                def wrapped_func(*args, **kwargs):
                    return func(self.agent, *args, **kwargs)
                
                # Create StructuredTool
                if tool_info["schema"]:
                    structured_tool = StructuredTool.from_function(
                        func=wrapped_func,
                        name=tool_name,
                        description=tool_info["description"],
                        args_schema=tool_info["schema"]
                    )
                else:
                    structured_tool = StructuredTool.from_function(
                        func=wrapped_func,
                        name=tool_name,
                        description=tool_info["description"]
                    )
                
                loaded_tools.append(structured_tool)
                
            except Exception as e:
                print(f"[Warning] Failed to create tool '{tool_name}': {e}")
                continue
        
        return loaded_tools


# ============================================================================
# ADDITIONAL TOOLS FOR TOOL MANAGEMENT
# ============================================================================

class DiscoverToolsInput(BaseModel):
    """Input for discovering tools."""
    pattern: str = Field(default="*", description="Pattern to filter tools (e.g., 'data_*' or '*')")


class CallCustomToolInput(BaseModel):
    """Input for calling custom tools."""
    tool_name: str = Field(..., description="Name of the tool file (without .py)")
    function_name: str = Field(..., description="Function name to call")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments as key-value pairs")


class ListToolFunctionsInput(BaseModel):
    """Input for listing functions in a tool."""
    tool_name: str = Field(..., description="Name of the tool file (without .py)")


def add_dynamic_tool_methods(tools_instance: 'LLMTools'):
    """
    Add dynamic tool loading methods to existing LLMTools instance.
    Call this function after creating your LLMTools instance.
    
    Usage:
        tools = LLMTools(agent)
        add_dynamic_tool_methods(tools)
    """
    
    # Initialize dynamic loader
    tools_instance.dynamic_loader = DynamicToolLoader(tools_instance.agent)
    
    def discover_custom_tools(self, pattern: str = "*") -> str:
        """
        Discover available custom tools in the tools directory.
        Returns a list of tool files and their functions.
        """
        try:
            tool_files = self.dynamic_loader.discover_tools(f"{pattern}.py")
            
            if not tool_files:
                return f"No tools found matching pattern '{pattern}'"
            
            output = [f"Found {len(tool_files)} custom tool(s):\n"]
            
            for tool_name in tool_files:
                try:
                    functions = self.dynamic_loader.list_tool_functions(tool_name)
                    output.append(f"\n📦 {tool_name}.py:")
                    
                    for func in functions:
                        decorator_mark = "🔧" if func["has_tool_decorator"] else "  "
                        output.append(f"  {decorator_mark} {func['name']}")
                        output.append(f"      {func['docstring'][:60]}")
                        
                        if func['parameters']:
                            params_str = ", ".join(
                                f"{p['name']}: {p['type']}" 
                                for p in func['parameters']
                            )
                            output.append(f"      Parameters: {params_str}")
                    
                except Exception as e:
                    output.append(f"  ⚠️  Error loading: {str(e)}")
            
            output.append("\n🔧 = Has @tool decorator (auto-loadable)")
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] {str(e)}"
    
    def call_custom_tool(self, tool_name: str, function_name: str, 
                        arguments: Dict[str, Any]) -> str:
        """
        Call a function from a custom tool file.
        
        Example:
            tool_name: "data_processing"
            function_name: "clean_csv"
            arguments: {"file_path": "data.csv", "remove_nulls": true}
        """
        try:
            result = self.dynamic_loader.call_tool_function(
                tool_name, function_name, arguments
            )
            
            # Store in memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                f"Called {tool_name}.{function_name}",
                "custom_tool_call",
                {"tool": tool_name, "function": function_name, "args": arguments}
            )
            
            return result
            
        except Exception as e:
            return f"[Custom Tool Error] {str(e)}"
    
    def list_tool_functions(self, tool_name: str) -> str:
        """
        List all functions available in a custom tool file.
        """
        try:
            functions = self.dynamic_loader.list_tool_functions(tool_name)
            
            output = [f"Functions in {tool_name}.py:\n"]
            
            for func in functions:
                output.append(f"\n📌 {func['name']}")
                output.append(f"   {func['docstring']}")
                
                if func['parameters']:
                    output.append("   Parameters:")
                    for param in func['parameters']:
                        default = f" = {param['default']}" if param['default'] else ""
                        output.append(f"     - {param['name']}: {param['type']}{default}")
                
                if func['has_tool_decorator']:
                    output.append("   🔧 Auto-loadable with @tool decorator")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"[Error] {str(e)}"
    
    def reload_custom_tools(self, _: str = "") -> str:
        """
        Reload all custom tool modules (useful after editing tool files).
        """
        try:
            # Clear loaded modules cache
            self.dynamic_loader.loaded_modules.clear()
            
            # Clear tool registry
            ToolRegistry.clear()
            
            # Reload all tools
            tools = self.dynamic_loader.auto_load_decorated_tools()
            
            return f"✓ Reloaded {len(tools)} custom tools"
            
        except Exception as e:
            return f"[Reload Error] {str(e)}"
    
    # Bind methods to the instance
    tools_instance.discover_custom_tools = lambda pattern="*": discover_custom_tools(tools_instance, pattern)
    tools_instance.call_custom_tool = lambda tool_name, function_name, arguments: call_custom_tool(tools_instance, tool_name, function_name, arguments)
    tools_instance.list_tool_functions = lambda tool_name: list_tool_functions(tools_instance, tool_name)
    tools_instance.reload_custom_tools = lambda _: reload_custom_tools(tools_instance, _)


def extend_tool_loader(agent):
    """
    Extend the ToolLoader function to include dynamic tool management.
    Add this to the END of your ToolLoader function.
    
    Usage in ToolLoader:
        tool_list = [ ... existing tools ... ]
        
        # Add dynamic tool loading
        dynamic_tools = extend_tool_loader(agent)
        tool_list.extend(dynamic_tools)
        
        return tool_list
    """
    tools = LLMTools(agent)
    add_dynamic_tool_methods(tools)
    
    # Create tools for managing custom tools
    management_tools = [
        StructuredTool.from_function(
            func=tools.discover_custom_tools,
            name="discover_tools",
            description="Discover and list available custom tools in the tools directory. Shows functions and their parameters.",
            args_schema=DiscoverToolsInput
        ),
        StructuredTool.from_function(
            func=tools.call_custom_tool,
            name="call_custom_tool",
            description="Call a function from a custom tool file. Provide tool name, function name, and arguments.",
            args_schema=CallCustomToolInput
        ),
        StructuredTool.from_function(
            func=tools.list_tool_functions,
            name="list_tool_functions",
            description="List all functions in a specific custom tool file with their parameters.",
            args_schema=ListToolFunctionsInput
        ),
        StructuredTool.from_function(
            func=tools.reload_custom_tools,
            name="reload_tools",
            description="Reload all custom tool modules. Use after editing tool files.",
        ),
    ]
    
    # Auto-load decorated tools from tools directory
    try:
        auto_loaded = tools.dynamic_loader.auto_load_decorated_tools()
        print(f"[Info] Auto-loaded {len(auto_loaded)} custom tools with @tool decorator")
        management_tools.extend(auto_loaded)
    except Exception as e:
        print(f"[Warning] Failed to auto-load custom tools: {e}")
    
    return management_tools



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