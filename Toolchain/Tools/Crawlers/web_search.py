"""
Web Search Tools - Extracted from tools.py
Provides web search, news search, and deep web search with full page scraping.

Usage in tools.py:
    from Vera.Toolchain.Tools.web_search import add_web_search_tools

    # In ToolLoader():
    add_web_search_tools(tool_list, agent)
"""

import os
import re
import json
import asyncio
import traceback
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus, urlparse

from langchain_core.tools import StructuredTool
from duckduckgo_search import DDGS
from playwright.async_api import async_playwright

from Vera.Toolchain.schemas import SearchInput, WebReportInput


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

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
# SEARCH ENGINE CONFIGURATIONS
# ============================================================================

SEARCH_ENGINE_CONFIGS = {
    "google": {
        "url_template": "https://www.google.com/search?q={}",
        "result_selector": "div.g",
        "title_selector": "h3",
        "link_selector": "a",
        "snippet_selector": "div[data-sncf], div.VwiC3b, span.aCOpRe",
    },
    "bing": {
        "url_template": "https://www.bing.com/search?q={}",
        "result_selector": "li.b_algo",
        "title_selector": "h2",
        "link_selector": "a",
        "snippet_selector": "p, .b_caption p",
    },
    "duckduckgo": {
        "url_template": "https://html.duckduckgo.com/html/?q={}",
        "result_selector": "div.result",
        "title_selector": "a.result__a",
        "link_selector": "a.result__a",
        "snippet_selector": "a.result__snippet",
    },
    "brave": {
        "url_template": "https://search.brave.com/search?q={}",
        "result_selector": "div.snippet",
        "title_selector": "div.title",
        "link_selector": "a",
        "snippet_selector": "div.snippet-description",
    },
    "perplexity": {
        "url_template": "https://www.perplexity.ai/search?q={}",
        "result_selector": "div[class*='result'], div[class*='Result']",
        "title_selector": "a, h3",
        "link_selector": "a",
        "snippet_selector": "div[class*='snippet'], p",
    },
}

FALLBACK_ORDER = {
    "google": ["duckduckgo", "bing"],
    "bing": ["duckduckgo", "google"],
    "duckduckgo": ["bing", "brave"],
    "brave": ["duckduckgo", "bing"],
    "perplexity": ["duckduckgo", "bing"],
}

CONSENT_SELECTORS = [
    'button:has-text("Accept")',
    'button:has-text("Agree")',
    'button:has-text("I agree")',
    'button:has-text("Accept all")',
    '[aria-label*="accept" i]',
    "#L2AGLb",  # Google specific
    'button[id*="accept"]',
    'button[class*="accept"]',
]


# ============================================================================
# WEB SEARCH TOOLS
# ============================================================================

class WebSearchTools:
    """Web search, news search, and deep search with full page scraping."""

    def __init__(self, agent):
        self.agent = agent

    # ------------------------------------------------------------------------
    # PLAYWRIGHT SEARCH (async helper)
    # ------------------------------------------------------------------------

    async def _playwright_search(
        self, query: str, search_engine: str, max_results: int
    ) -> List[Dict[str, str]]:
        """
        Perform web search using Playwright for maximum robustness.
        Supports multiple search engines with fallback mechanisms.
        """
        config = SEARCH_ENGINE_CONFIGS.get(search_engine.lower())
        if not config:
            raise ValueError(f"Unsupported search engine: {search_engine}")

        url = config["url_template"].format(quote_plus(query))
        results = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                )
                await context.add_init_script(
                    """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    """
                )

                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)

                # Handle cookie consent dialogs
                for selector in CONSENT_SELECTORS:
                    try:
                        button = await page.query_selector(selector)
                        if button and await button.is_visible():
                            await button.click()
                            await page.wait_for_timeout(1000)
                            break
                    except:
                        continue

                # Wait for results
                try:
                    await page.wait_for_selector(
                        config["result_selector"], timeout=10000
                    )
                except:
                    await page.wait_for_timeout(3000)

                # Extract results
                result_elements = await page.query_selector_all(
                    config["result_selector"]
                )

                for result_elem in result_elements[:max_results]:
                    try:
                        title = ""
                        title_elem = await result_elem.query_selector(
                            config["title_selector"]
                        )
                        if title_elem:
                            title = (await title_elem.inner_text()).strip()

                        href = ""
                        link_elem = await result_elem.query_selector(
                            config["link_selector"]
                        )
                        if link_elem:
                            href = await link_elem.get_attribute("href")
                            href = self._clean_url(href, url, search_engine)

                        snippet = ""
                        snippet_elem = await result_elem.query_selector(
                            config["snippet_selector"]
                        )
                        if snippet_elem:
                            snippet = (await snippet_elem.inner_text()).strip()

                        if title and href and href.startswith("http"):
                            results.append(
                                {"title": title, "href": href, "body": snippet}
                            )
                    except:
                        continue

                await browser.close()

        except Exception as e:
            raise Exception(f"Search failed for {search_engine}: {str(e)}")

        return results

    @staticmethod
    def _clean_url(href: str, base_url: str, engine: str) -> str:
        """Clean and normalise a URL extracted from search results."""
        if not href:
            return ""

        # Handle relative URLs
        if href.startswith("/"):
            parsed = urlparse(base_url)
            href = f"{parsed.scheme}://{parsed.netloc}{href}"

        # DuckDuckGo redirect URLs
        if "duckduckgo.com" in href and "/l/?uddg=" in href:
            try:
                from urllib.parse import unquote

                href = unquote(href.split("/l/?uddg=")[1].split("&")[0])
            except:
                pass

        # Google redirect URLs
        if engine == "google" and "/url?q=" in href:
            try:
                from urllib.parse import unquote

                href = unquote(href.split("/url?q=")[1].split("&")[0])
            except:
                pass

        return href

    # ------------------------------------------------------------------------
    # PUBLIC SEARCH METHODS
    # ------------------------------------------------------------------------

    def search_web(
        self,
        query: str,
        max_results: int = 10,
        search_engine: str = "duckduckgo",
    ) -> str:
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
        engines_to_try = [search_engine] + FALLBACK_ORDER.get(
            search_engine, ["duckduckgo"]
        )

        results = []
        last_error = None

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        for engine in engines_to_try:
            try:
                results = loop.run_until_complete(
                    self._playwright_search(query, engine, max_results)
                )
                if results:
                    search_engine = engine
                    break
            except Exception as e:
                last_error = str(e)
                continue

        if not results:
            return f"[Search Error] All search engines failed. Last error: {last_error}"

        try:
            search_mem = self.agent.mem.add_session_memory(
                self.agent.sess.id,
                query,
                "web_search",
                metadata={
                    "search_engine": search_engine,
                    "type": "playwright_search",
                },
            )

            output = []
            for idx, r in enumerate(results, 1):
                title = r.get("title", "No title")
                href = r.get("href", "")
                body = r.get("body", "No description")

                result_entity = self.agent.mem.upsert_entity(
                    href,
                    "search_result",
                    properties={
                        "title": title,
                        "body": body,
                        "engine": search_engine,
                    },
                    labels=["SearchResult"],
                )
                self.agent.mem.link(search_mem.id, result_entity.id, "RESULT")

                output.append(
                    f"{idx}. {title}\n   URL: {href}\n   {body}\n"
                )

            footer = f"\n[Searched using {search_engine.title()} • {len(results)} results found]"
            return "\n".join(output) + footer

        except Exception:
            # Return results even if memory storage fails
            output = []
            for idx, r in enumerate(results, 1):
                output.append(
                    f"{idx}. {r.get('title', 'No title')}\n"
                    f"   URL: {r.get('href', '')}\n"
                    f"   {r.get('body', '')}\n"
                )
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
                    self.agent.sess.id,
                    query,
                    "news_search",
                    metadata={"search_engine": "duckduckgo", "type": "news"},
                )

                output = []
                for idx, r in enumerate(results, 1):
                    title = r.get("title", "No title")
                    href = r.get("url", "")
                    body = r.get("body", "No description")
                    date = r.get("date", "Unknown date")

                    result_entity = self.agent.mem.upsert_entity(
                        href,
                        "news_result",
                        properties={"title": title, "body": body, "date": date},
                        labels=["NewsResult"],
                    )
                    self.agent.mem.link(search_mem.id, result_entity.id, "RESULT")

                    output.append(
                        f"{idx}. [{date}] {title}\n   URL: {href}\n   {body}\n"
                    )

                return "\n".join(output) if output else "No news found."

        except Exception as e:
            return f"[News Search Error] {str(e)}"

    # ------------------------------------------------------------------------
    # DEEP SEARCH (with full-page scraping)
    # ------------------------------------------------------------------------

    async def _scrape_url(self, url: str) -> str:
        """Scrape a single URL using Playwright and return cleaned text."""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36"
                    )
                )
                page = await context.new_page()
                await page.goto(
                    url, wait_until="domcontentloaded", timeout=20000
                )
                await page.wait_for_timeout(2000)

                # Handle cookie consent
                for selector in CONSENT_SELECTORS[:3]:
                    try:
                        button = await page.query_selector(selector)
                        if button and await button.is_visible():
                            await button.click()
                            await page.wait_for_timeout(1000)
                            break
                    except:
                        continue

                # Extract main content
                content_text = ""
                for selector in [
                    "article",
                    "main",
                    '[role="main"]',
                    ".article",
                    ".content",
                    ".post",
                ]:
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
                    paragraphs = await page.query_selector_all("p")
                    para_texts = []
                    for para in paragraphs:
                        try:
                            text = await para.inner_text()
                            if len(text) > 50:
                                para_texts.append(text)
                        except:
                            continue
                    content_text = "\n\n".join(para_texts)

                await browser.close()

                # Clean text
                lines = (line.strip() for line in content_text.splitlines())
                chunks = (
                    phrase.strip()
                    for line in lines
                    for phrase in line.split("  ")
                )
                cleaned = " ".join(chunk for chunk in chunks if chunk)
                cleaned = re.sub(r"\s+", " ", cleaned).strip()

                return (
                    truncate_output(cleaned, 2500)
                    if cleaned
                    else "[No content extracted]"
                )

        except Exception as e:
            return f"[Scraping Error: {str(e)[:100]}]"

    def web_search_deep(self, query: str, max_results: int = 5) -> str:
        """
        Comprehensive web search that scrapes full page content.
        Accepts search queries or existing search result text.
        Returns detailed reports with full page content from each result.
        Use when you need in-depth information from web pages.
        """
        try:
            # Determine if input is query or existing results
            if re.search(r"^\d+\.\s+.+", input_data) and "http" in input_data:
                results = self._parse_search_results(input_data)
                search_query = "parsed_results"
            else:
                with DDGS() as ddgs:
                    results = list(
                        ddgs.text(input_data, region="us-en", max_results=max_results)
                    )
                search_query = input_data

            if not results:
                return "No results to process."

            search_mem = self.agent.mem.add_session_memory(
                self.agent.sess.id,
                search_query,
                "deep_web_search",
                metadata={"type": "deep_search", "max_results": max_results},
            )

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

                result_entity = self.agent.mem.upsert_entity(
                    href,
                    "deep_search_result",
                    properties={"title": title, "body": body},
                    labels=["DeepSearchResult"],
                )
                self.agent.mem.link(search_mem.id, result_entity.id, "RESULT")

                output.append(
                    f"\n{'=' * 80}\n"
                    f"RESULT {idx}: {title}\n"
                    f"URL: {href}\n"
                    f"Description: {body}\n"
                    f"{'-' * 40}"
                )

                scraped = loop.run_until_complete(self._scrape_url(href))
                output.append(f"Content:\n{scraped}\n{'=' * 80}")

                content_entity = self.agent.mem.upsert_entity(
                    f"{href}_content",
                    "scraped_content",
                    properties={
                        "title": title,
                        "url": href,
                        "preview": scraped[:500],
                    },
                    labels=["ScrapedContent"],
                )
                self.agent.mem.link(
                    result_entity.id, content_entity.id, "HAS_CONTENT"
                )

            return "\n".join(output)

        except Exception as e:
            return f"[Deep Search Error] {str(e)}"

    @staticmethod
    def _parse_search_results(text: str) -> List[Dict[str, str]]:
        """Parse search results from text format back into dicts."""
        results = []
        lines = text.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            if re.match(r"^\d+\.\s+.+", line):
                title = line.split(". ", 1)[1] if ". " in line else line
                url = (
                    lines[i + 1].strip()
                    if i + 1 < len(lines) and lines[i + 1].startswith("http")
                    else ""
                )
                body = lines[i + 2].strip() if i + 2 < len(lines) else ""

                if url:
                    results.append({"title": title, "href": url, "body": body})
                i += 3
            else:
                i += 1

        return results


# ============================================================================
# TOOL LOADER INTEGRATION
# ============================================================================

def add_web_search_tools(tool_list: List, agent) -> List:
    """
    Add web search tools to the tool list.

    Call this in ToolLoader():
        from Vera.Toolchain.Tools.web_search import add_web_search_tools
        add_web_search_tools(tool_list, agent)
    """
    tools = WebSearchTools(agent)

    tool_list.extend(
        [
            StructuredTool.from_function(
                func=tools.search_web,
                name="web_search",
                description=(
                    "Advanced web search using Playwright for robustness. "
                    "Supports multiple search engines with automatic fallback."
                ),
                args_schema=SearchInput,
            ),
            StructuredTool.from_function(
                func=tools.search_news,
                name="news_search",
                description=(
                    "Search recent news using DuckDuckGo News. "
                    "Best for current events."
                ),
                args_schema=SearchInput,
            ),
            StructuredTool.from_function(
                func=tools.web_search_deep,
                name="web_search_deep",
                description=(
                    "Comprehensive web search with full page scraping. "
                    "Use for in-depth information."
                ),
                args_schema=WebReportInput,
            ),
        ]
    )

    return tool_list