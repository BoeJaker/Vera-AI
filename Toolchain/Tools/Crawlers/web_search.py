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
    # ENHANCED PAGE SCRAPING (shared by search_web and search_news)
    # ------------------------------------------------------------------------

    async def _scrape_url_with_links(self, url: str, max_content: int = 1500) -> Dict[str, Any]:
        """
        Scrape a page and return both cleaned body text AND all meaningful
        in-body links (anchor text + href).

        Returns a dict:
            {
                "text":  <cleaned body text, truncated>,
                "links": [{"text": ..., "href": ...}, ...]   # up to 20 links
            }

        This is intentionally separate from the existing _scrape_url() so that
        method's behaviour (used by web_search_deep) is not affected.
        """
        result = {"text": "[No content extracted]", "links": []}
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
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(2000)

                # Dismiss cookie consent banners so they don't pollute extracted text
                for selector in CONSENT_SELECTORS[:3]:
                    try:
                        button = await page.query_selector(selector)
                        if button and await button.is_visible():
                            await button.click()
                            await page.wait_for_timeout(1000)
                            break
                    except:
                        continue

                # ── Extract main body text ────────────────────────────────────
                # Try semantic content containers first; fall back to <p> tags
                content_text = ""
                for selector in ["article", "main", '[role="main"]', ".article", ".content", ".post"]:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            text = await element.inner_text()
                            if len(text) > 200:
                                content_text = text
                                break
                    except:
                        continue

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

                # Normalise whitespace
                lines = (line.strip() for line in content_text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                cleaned = " ".join(chunk for chunk in chunks if chunk)
                cleaned = re.sub(r"\s+", " ", cleaned).strip()
                result["text"] = truncate_output(cleaned, max_content) if cleaned else "[No content extracted]"

                # ── Extract in-body links ─────────────────────────────────────
                # Scope link extraction to the same semantic containers used for
                # text so we only surface links that are genuinely part of the
                # article/main content rather than nav/footer noise.
                #
                # Strategy:
                #   1. Find the best content container (same priority order above)
                #   2. Query all <a href> elements inside it
                #   3. Filter: skip empty text, anchors (#), mailto/tel, very
                #      short labels (likely icon-only links), and duplicates
                #   4. Resolve relative URLs against the page origin

                parsed_base = urlparse(url)
                base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"

                # Re-locate the content container (can't reuse the handle across
                # the content extraction block due to potential stale references)
                container = None
                for selector in ["article", "main", '[role="main"]', ".article", ".content", ".post"]:
                    try:
                        el = await page.query_selector(selector)
                        if el:
                            container = el
                            break
                    except:
                        continue

                # Fall back to whole <body> if no container found
                if container is None:
                    container = await page.query_selector("body")

                links = []
                seen_hrefs = set()

                if container:
                    anchor_elements = await container.query_selector_all("a[href]")
                    for anchor in anchor_elements:
                        try:
                            href = (await anchor.get_attribute("href") or "").strip()
                            text = (await anchor.inner_text()).strip()

                            # Skip empty, anchor-only, or non-http/relative links
                            if not href or href.startswith("#"):
                                continue
                            if href.startswith("mailto:") or href.startswith("tel:"):
                                continue
                            # Skip very short labels that are usually icon buttons
                            if len(text) < 3:
                                continue

                            # Resolve relative URLs
                            if href.startswith("/"):
                                href = base_origin + href
                            elif not href.startswith("http"):
                                # e.g. "../something" — skip malformed ones
                                continue

                            # Deduplicate by href
                            if href in seen_hrefs:
                                continue
                            seen_hrefs.add(href)

                            links.append({"text": text, "href": href})

                            # Cap at 20 links to keep output manageable
                            if len(links) >= 20:
                                break
                        except:
                            continue

                result["links"] = links
                await browser.close()

        except Exception as e:
            result["text"] = f"[Scraping Error: {str(e)[:100]}]"

        return result

    @staticmethod
    def _format_scraped(scraped: Dict[str, Any]) -> str:
        """
        Format the dict returned by _scrape_url_with_links() into a readable
        block that can be appended to a search result entry.

        Output sections:
            Page Content: <body text>
            In-Page Links:
              - Link text → https://...
              ...
        """
        lines = []

        text = scraped.get("text", "")
        if text and text != "[No content extracted]":
            lines.append(f"   Page Content:\n      {text}")

        links = scraped.get("links", [])
        if links:
            lines.append("   In-Page Links:")
            for link in links:
                lines.append(f"      - {link['text']} → {link['href']}")

        return "\n".join(lines)

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
        Returns titles, URLs, descriptions, full page text, and in-body links
        from each search result.

        Features:
        - Bypasses bot detection
        - Handles cookie consent
        - Extracts clean URLs
        - Falls back to alternative engines on failure
        - Scrapes full page content and in-body links for each result
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
                href  = r.get("href", "")
                body  = r.get("body", "No description")

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

                # ── NEW: scrape full page content + in-body links ─────────────
                # Each result page is scraped to surface richer information than
                # the search-engine snippet alone.  We use a modest max_content
                # of 1500 chars per page so the total output stays manageable
                # across up to 10 results (≈15 000 chars of page text max).
                scraped = loop.run_until_complete(
                    self._scrape_url_with_links(href, max_content=1500)
                )

                # Persist the scraped preview and links in the knowledge graph
                content_entity = self.agent.mem.upsert_entity(
                    f"{href}_content",
                    "scraped_content",
                    properties={
                        "title": title,
                        "url": href,
                        "preview": scraped["text"][:500],
                        "link_count": len(scraped["links"]),
                    },
                    labels=["ScrapedContent"],
                )
                self.agent.mem.link(result_entity.id, content_entity.id, "HAS_CONTENT")
                # ─────────────────────────────────────────────────────────────

                output.append(
                    f"{idx}. {title}\n"
                    f"   URL: {href}\n"
                    f"   Snippet: {body}\n"
                    f"{self._format_scraped(scraped)}\n"
                )

            footer = f"\n[Searched using {search_engine.title()} • {len(results)} results found]"
            return "\n".join(output) + footer

        except Exception:
            # Return results even if memory storage fails; still attempt scraping
            output = []
            for idx, r in enumerate(results, 1):
                href = r.get("href", "")
                scraped = {}
                if href:
                    try:
                        scraped = loop.run_until_complete(
                            self._scrape_url_with_links(href, max_content=1500)
                        )
                    except Exception:
                        pass
                output.append(
                    f"{idx}. {r.get('title', 'No title')}\n"
                    f"   URL: {href}\n"
                    f"   {r.get('body', '')}\n"
                    f"{self._format_scraped(scraped) if scraped else ''}\n"
                )
            return "\n".join(output)

    def search_news(self, query: str, max_results: int = 10) -> str:
        """
        Search for recent news articles using DuckDuckGo News.
        Best for current events and recent developments.
        Returns article text and in-body links scraped from each result page.
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

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
                    href  = r.get("url", "")
                    body  = r.get("body", "No description")
                    date  = r.get("date", "Unknown date")

                    result_entity = self.agent.mem.upsert_entity(
                        href,
                        "news_result",
                        properties={"title": title, "body": body, "date": date},
                        labels=["NewsResult"],
                    )
                    self.agent.mem.link(search_mem.id, result_entity.id, "RESULT")

                    # ── NEW: scrape full article text + in-body links ──────────
                    # News articles often contain the full story and related-
                    # article links that are highly relevant to the query topic.
                    # We cap content at 2000 chars (articles are usually denser
                    # and more valuable than generic search result pages).
                    scraped = {}
                    if href:
                        try:
                            scraped = loop.run_until_complete(
                                self._scrape_url_with_links(href, max_content=2000)
                            )
                        except Exception:
                            pass

                    if scraped:
                        content_entity = self.agent.mem.upsert_entity(
                            f"{href}_content",
                            "scraped_content",
                            properties={
                                "title": title,
                                "url": href,
                                "preview": scraped["text"][:500],
                                "link_count": len(scraped.get("links", [])),
                            },
                            labels=["ScrapedContent"],
                        )
                        self.agent.mem.link(result_entity.id, content_entity.id, "HAS_CONTENT")
                    # ─────────────────────────────────────────────────────────

                    output.append(
                        f"{idx}. [{date}] {title}\n"
                        f"   URL: {href}\n"
                        f"   Snippet: {body}\n"
                        f"{self._format_scraped(scraped) if scraped else ''}\n"
                    )

                return "\n".join(output) if output else "No news found."

        except Exception as e:
            return f"[News Search Error] {str(e)}"

    # ------------------------------------------------------------------------
    # DEEP SEARCH (with full-page scraping)
    # ------------------------------------------------------------------------

    async def _scrape_url(self, url: str) -> str:
        """
        Scrape a single URL using Playwright and return cleaned text.
        Used exclusively by web_search_deep — unchanged from original.
        """
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
        # ── BUG FIX: original used undefined `input_data`; use `query` ────────
        input_data = query
        # ─────────────────────────────────────────────────────────────────────

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
                href  = r.get("href", "")
                body  = r.get("body", "")

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
                    "Supports multiple search engines with automatic fallback. "
                    "Returns full page content and in-body links from each result."
                ),
                args_schema=SearchInput,
            ),
            StructuredTool.from_function(
                func=tools.search_news,
                name="news_search",
                description=(
                    "Search recent news using DuckDuckGo News. "
                    "Best for current events. "
                    "Returns article text and in-body links from each result page."
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