"""
researcher_api.py  —  Vera Research Agent v4
─────────────────────────────────────────────
New in v4:
  • Full database persistence via db.py
    - SQLite by default (vera_research.db)
    - PostgreSQL via VERA_DB_URL env var
  • All jobs, citations, projects, rounds, sources, config saved on completion
  • /api/history now reads from DB (survives restarts)
  • /api/db/stats  — live DB statistics
  • /api/db/search — full-text search across all saved research
  • Sources & instance config loaded from DB on startup

Run:
    python researcher_api.py
    python -m Vera.ChatUI.researcher_api
    uvicorn Vera.ChatUI.researcher_api:app --host 0.0.0.0 --port 8765 --reload

DB config:
    VERA_DB_URL=postgresql+asyncpg://user:pass@host/vera  (optional — SQLite default)
    VERA_SQLITE_PATH=./vera_research.db                   (optional)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import AsyncIterator, Optional
from urllib.parse import urlparse, urljoin

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from Vera.ChatUI.research_db import DB  # local persistence layer

log = logging.getLogger("vera.researcher")
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

SCREENSHOT_DIR = Path("screenshots")
PROJECTS_DIR   = Path("projects")
SCREENSHOT_DIR.mkdir(exist_ok=True)
PROJECTS_DIR.mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
#  Enums
# ══════════════════════════════════════════════════════════════════════════════

class ModelTier(str, Enum):
    THINKER = "thinker"
    WRITER  = "writer"
    ANALYST = "analyst"
    AUTO    = "auto"

class AgentMode(str, Enum):
    SINGLE   = "single"
    PARALLEL = "parallel"
    DEEP     = "deep"

class SourceType(str, Enum):
    WEB_SEARCH  = "web_search"
    WEB_CRAWL   = "web_crawl"
    WEB_ARCHIVE = "web_archive"
    NEO4J       = "neo4j"
    CHROMA      = "chroma"
    GITHUB      = "github"
    NEWS        = "news"
    REDIS       = "redis"
    DATABASE    = "database"
    CUSTOM      = "custom"

class JobStatus(str, Enum):
    QUEUED    = "queued"
    THINKING  = "thinking"
    SEARCHING = "searching"
    CRAWLING  = "crawling"
    ARCHITECTING = "architecting"
    CODING    = "coding"
    REVIEWING = "reviewing"
    WRITING   = "writing"
    VERIFYING = "verifying"
    CHAINING  = "chaining"    # waiting for next chain run
    DONE      = "done"
    ERROR     = "error"
    CANCELLED = "cancelled"

class OutputMode(str, Enum):
    REPORT    = "report"      # normal markdown report
    GUIDE     = "guide"       # multi-section long-form guide
    FILESTORE = "filestore"   # produces a full file-tree + content
    CODE      = "code"        # research → architect → implement → review → chain

# ══════════════════════════════════════════════════════════════════════════════
#  Dataclasses
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class OllamaInstance:
    name: str
    host: str
    port: int
    tier: ModelTier
    model: str
    ctx_size: int = 8192
    enabled: bool = True

    @property
    def base_url(self):  return f"http://{self.host}:{self.port}"
    @property
    def generate_url(self): return f"{self.base_url}/api/generate"
    @property
    def tags_url(self):  return f"{self.base_url}/api/tags"


@dataclass
class DataSource:
    id: str
    label: str
    type: SourceType
    enabled: bool
    config: dict = field(default_factory=dict)
    status: str = "unknown"


@dataclass
class WebSearchConfig:
    """Configurable web search behaviour."""
    engine:       str   = "searxng"    # searxng | brave | ddg
    result_count: int   = 8
    crawl_depth:  int   = 1            # 0=no crawl, 1=linked pages, 2=deep
    crawl_breadth:int   = 3            # pages per crawled link
    crawl_timeout:float = 8.0
    include_archive: bool = False
    safe_search:  int   = 0


@dataclass
class Citation:
    id: str
    url: str
    title: str
    snippet: str
    source_type: str
    screenshot_path: str = ""
    domain: str = ""
    full_text: str = ""          # populated by deep crawl
    fetched_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if self.url and not self.domain:
            try: self.domain = urlparse(self.url).netloc
            except Exception: pass

    def to_dict(self, include_full_text: bool = False):
        d = asdict(self)
        d["screenshot_url"] = f"/screenshots/{self.screenshot_path}" if self.screenshot_path else ""
        if not include_full_text:
            d.pop("full_text", None)  # strip for WS to keep messages small
        return d

    def to_dict_full(self):
        """Full serialisation including crawled text — for DB storage."""
        return self.to_dict(include_full_text=True)


@dataclass
class ProjectRound:
    id: str
    job_id: str
    round_num: int
    query: str
    result: str
    citations: list[dict]
    created_at: float = field(default_factory=time.time)


@dataclass
class Project:
    id: str
    name: str
    description: str
    output_mode: OutputMode
    rounds: list[ProjectRound] = field(default_factory=list)
    context_summary: str = ""    # rolling summary updated after each round
    file_tree: dict = field(default_factory=dict)  # path → content for filestore
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "output_mode": self.output_mode, "round_count": len(self.rounds),
            "context_summary": self.context_summary[:400],
            "file_count": len(self.file_tree),
            "created_at": self.created_at, "updated_at": self.updated_at,
        }


@dataclass
class AgentSlot:
    id: str
    tier: ModelTier
    job_id: Optional[str] = None
    status: str = "idle"
    model: str = ""
    tokens: int = 0
    started_at: Optional[float] = None


@dataclass
class ChainContext:
    """
    Passed between chained coding runs so each run knows exactly what
    has been built and what remains — without needing the full prior
    output in its context window.
    """
    chain_id:       str                       # shared across all runs in a chain
    run_number:     int                       # 1-based
    original_task:  str                       # the original user request, never changes
    architecture:   str  = ""                # full arch plan (set in run 1, carried forward)
    files_planned:  list[str] = field(default_factory=list)   # every file in the plan
    files_done:     list[str] = field(default_factory=list)   # files completed so far
    files_pending:  list[str] = field(default_factory=list)   # files still to write
    continuity_summary: str = ""             # thinker's rolling "state of play" summary
    accumulated_code: dict[str, str] = field(default_factory=dict)  # path → content so far
    research_context: str = ""               # source/research findings carried forward
    is_complete:    bool = False             # set true when files_pending is empty


@dataclass
class ResearchJob:
    id: str
    query: str
    mode: AgentMode
    output_mode: OutputMode
    sources: list[str]
    status: JobStatus
    created_at: float
    project_id: Optional[str] = None
    finished_at: Optional[float] = None
    result: Optional[str] = None
    error: Optional[str] = None
    steps: list[dict] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    token_count: int = 0
    file_tree: dict = field(default_factory=dict)   # path → content
    # Iterative context — passed from prior research run
    prior_context: str = ""        # text of previous result
    context_mode:  str = "fresh"   # "fresh" | "continue"
    # Chain fields (only set for CODE mode)
    chain_ctx: Optional[ChainContext] = None
    chain_continues: bool = False   # True when more runs needed

# ══════════════════════════════════════════════════════════════════════════════
#  Defaults
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_INSTANCES: list[OllamaInstance] = [
    OllamaInstance("Thinker", "192.168.0.247", 11435, ModelTier.THINKER, "qwen3.5:9b", 131072),
    OllamaInstance("Writer",  "192.168.0.250", 11435, ModelTier.WRITER,  "qwen3.5:9b",  32768),
    OllamaInstance("Analyst", "192.168.0.246", 11436, ModelTier.ANALYST, "qwen3.5:9b",           32768, enabled=True),
]

DEFAULT_SOURCES: list[DataSource] = [
    DataSource("searxng",     "SearXNG",         SourceType.WEB_SEARCH,  True,  {"host":"http://llm.int:8888"}),
    DataSource("brave",       "Brave Search",    SourceType.WEB_SEARCH,  False, {"api_key":""}),
    DataSource("crawl4ai",    "Web Crawl",       SourceType.WEB_CRAWL,   True,  {}),
    DataSource("commoncrawl", "Common Crawl",    SourceType.WEB_ARCHIVE, False, {}),
    DataSource("wayback",     "Wayback Machine", SourceType.WEB_ARCHIVE, True,  {}),
    DataSource("neo4j",       "Neo4j Graph",     SourceType.NEO4J,       True,  {"uri":"bolt://llm.int:7687","user":"neo4j","password":""}),
    DataSource("chroma",      "ChromaDB",        SourceType.CHROMA,      True,  {"host":"llm.int","port":8000}),  # set "directory" to a local path (or glob) to use PersistentClient instead
    DataSource("github",      "GitHub",          SourceType.GITHUB,      False, {"token":""}),
    DataSource("hackernews",  "Hacker News",     SourceType.NEWS,        True,  {}),
    DataSource("arxiv",       "arXiv",           SourceType.NEWS,        True,  {}),
    DataSource("redis",       "Redis",           SourceType.REDIS,       False, {"host":"llm.int","port":6379,"password":"","db":0,"prefix":"vera:"}),
]

# ══════════════════════════════════════════════════════════════════════════════
#  Global state
# ══════════════════════════════════════════════════════════════════════════════

instances:     list[OllamaInstance]       = list(DEFAULT_INSTANCES)
sources:       list[DataSource]           = list(DEFAULT_SOURCES)
web_cfg:       WebSearchConfig            = WebSearchConfig()
jobs:          dict[str, ResearchJob]     = {}
history:       list[ResearchJob]          = []
projects:      dict[str, Project]         = {}
ws_clients:    dict[str, list[WebSocket]] = {}
cancel_flags:  dict[str, bool]            = {}

agent_slots: list[AgentSlot] = [
    AgentSlot("slot-thinker", ModelTier.THINKER),
    AgentSlot("slot-writer",  ModelTier.WRITER),
    AgentSlot("slot-analyst", ModelTier.ANALYST),
]

# ══════════════════════════════════════════════════════════════════════════════
#  Screenshot
# ══════════════════════════════════════════════════════════════════════════════
# ── Playwright — import once at module level ──────────────────────────────────
# Never import inside _get_browser: concurrent coroutines calling it simultaneously
# exhaust Python's recursion limit during the first-time module import.
_async_playwright = None
_playwright_available = False

try:
    from playwright.async_api import async_playwright as _async_playwright
    _playwright_available = True
    log.info("playwright imported OK")
except Exception as e:
    log.warning("playwright import failed — screenshots will use image extraction / SVG: %s", e)

_pw_browser = None
_pw_lock = asyncio.Lock()
_screenshot_sem = asyncio.Semaphore(2)


async def _get_browser():
    global _pw_browser

    if not _playwright_available:
        raise RuntimeError("playwright not available (import failed at startup)")

    async with _pw_lock:
        if _pw_browser is not None:
            try:
                if not _pw_browser.is_connected():
                    raise RuntimeError("browser disconnected")
                return _pw_browser
            except Exception as e:
                log.warning("Browser dead, relaunching: %s", e)
                try:
                    await _pw_browser.close()
                except Exception:
                    pass
                _pw_browser = None

        try:
            log.info("Launching Playwright Chromium…")
            pw = await _async_playwright().start()
            _pw_browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-extensions",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            log.info("✓ Playwright browser ready (connected=%s)", _pw_browser.is_connected())
            return _pw_browser
        except Exception as e:
            log.error("Failed to launch Playwright browser: %s", e, exc_info=True)
            raise

async def capture_screenshot(url: str) -> str:
    """
    Capture a screenshot of *url*, trying three methods in order:
        1. Playwright headless Chromium
        2. OG/twitter meta image extraction
        3. SVG placeholder (last resort)

    Results are cached by URL hash. Stale SVG placeholders are deleted on
    each call so real screenshots can replace them on retry.
    Always returns a filename — never raises.
    """
    key = hashlib.md5(url.encode()).hexdigest()[:16]
    png_path = SCREENSHOT_DIR / f"{key}.png"
    svg_path = SCREENSHOT_DIR / f"{key}.svg"

    if png_path.exists():
        log.debug("Screenshot cache hit: %s → %s", url[:60], png_path.name)
        return png_path.name

    # Delete stale SVG so we always retry real capture
    if svg_path.exists():
        svg_path.unlink(missing_ok=True)
        log.debug("Removed stale SVG, retrying capture for: %s", url[:60])

    page_title = url[:70]

    # ── 1. Playwright (semaphore-limited to 2 concurrent pages) ──────────────
    async with _screenshot_sem:
        try:
            browser = await _get_browser()
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-GB,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Upgrade-Insecure-Requests": "1",
                },
                java_script_enabled=True,
                ignore_https_errors=True,
            )
            page = await context.new_page()
            try:
                target_url = url if url.startswith(("http://", "https://")) else f"https://{url}"
                log.debug("Playwright navigating: %s", target_url[:80])
                await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass  # networkidle timeout is fine — page is rendered enough
                await page.screenshot(path=str(png_path), full_page=False, type="png")
                log.info("✓ Screenshot (playwright): %s → %s", url[:60], png_path.name)
                return png_path.name
            except Exception as e:
                log.warning("Playwright page error for %s: %s", url[:60], e)
                try:
                    page_title = (await page.title())[:70] or page_title
                except Exception:
                    pass
            finally:
                try:
                    await page.close()
                except Exception:
                    pass
                try:
                    await context.close()
                except Exception:
                    pass
        except Exception as e:
            log.error("Playwright browser error for %s: %s", url[:60], e)
            # Only kill the shared browser for genuine browser-level failures
            global _pw_browser
            if not _pw_browser or not _pw_browser.is_connected():
                _pw_browser = None

    # ── 2. Meta image extraction ──────────────────────────────────────────────
    try:
        log.debug("Trying image extraction for: %s", url[:60])
        async with httpx.AsyncClient(
            timeout=10.0, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Vera/1.0)"},
        ) as c:
            r = await c.get(url)
            html = r.text[:80000]

        tm = re.search(r"<title[^>]*>([^<]{0,120})</title>", html, re.I)
        if tm:
            page_title = tm.group(1).strip()[:70]

        image_url = None
        for pat in [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\'>\s]+)["\']',
            r'<meta[^>]+content=["\']([^"\'>\s]+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\'>\s]+)["\']',
            r'<meta[^>]+content=["\']([^"\'>\s]+)["\'][^>]+name=["\']twitter:image["\']',
            r'<meta[^>]+name=["\']thumbnail["\'][^>]+content=["\']([^"\'>\s]+)["\']',
        ]:
            m = re.search(pat, html, re.I)
            if m:
                image_url = m.group(1).strip()
                log.debug("Found meta image: %s", image_url[:80])
                break

        if not image_url:
            for m in re.finditer(r'<img[^>]+src=["\']([^"\'>\s]+)["\'][^>]*>', html, re.I):
                src = m.group(1).strip()
                if src.startswith("data:"):
                    continue
                w = re.search(r'width=["\'](\d+)["\']', m.group(0), re.I)
                h = re.search(r'height=["\'](\d+)["\']', m.group(0), re.I)
                if w and int(w.group(1)) < 100:
                    continue
                if h and int(h.group(1)) < 100:
                    continue
                image_url = src
                log.debug("Found <img>: %s", image_url[:80])
                break

        if image_url:
            image_url = image_url.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            if image_url.startswith("//"):
                image_url = "https:" + image_url
            elif image_url.startswith("/"):
                p = urlparse(url)
                image_url = f"{p.scheme}://{p.netloc}{image_url}"
            elif not image_url.startswith(("http://", "https://")):
                image_url = urljoin(url, image_url)

        if image_url and image_url.startswith(("http://", "https://")):
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as c:
                img_resp = await c.get(image_url, headers={"User-Agent": "Mozilla/5.0"})
                ct = img_resp.headers.get("content-type", "").lower()
                if (any(ct.startswith(f"image/{t}") for t in
                        ("jpeg", "jpg", "png", "webp", "gif", "avif"))
                        and len(img_resp.content) > 5000):
                    png_path.write_bytes(img_resp.content)
                    log.info("✓ Screenshot (meta image): %s → %s", url[:60], png_path.name)
                    return png_path.name
                else:
                    log.debug("Meta image rejected: ct=%s size=%d", ct, len(img_resp.content))

    except Exception as e:
        log.warning("Image extraction failed for %s: %s", url[:60], e)

    # ── 3. SVG placeholder ────────────────────────────────────────────────────
    log.warning("All capture methods failed for %s — writing SVG placeholder", url[:60])
    domain = urlparse(url).netloc or url[:40]
    title_display = page_title[:60] + ("…" if len(page_title) > 60 else "")

    def ex(s: str) -> str:
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    svg_path.write_text(f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="380">
  <rect width="640" height="380" fill="#e8e5df"/>
  <rect width="640" height="34" fill="#dddad3"/>
  <circle cx="16" cy="17" r="5" fill="#c03030" opacity=".55"/>
  <circle cx="29" cy="17" r="5" fill="#c47020" opacity=".55"/>
  <circle cx="42" cy="17" r="5" fill="#228060" opacity=".55"/>
  <rect x="55" y="9" width="530" height="16" rx="8" fill="#f0ede8"/>
  <text x="320" y="20" font-family="monospace" font-size="10" fill="#a8a69e" text-anchor="middle">{ex(domain)}</text>
  <rect x="40" y="54" width="560" height="260" rx="5" fill="#f0ede8"/>
  <text x="320" y="170" font-family="monospace" font-size="14" fill="#1a1a18" text-anchor="middle" font-weight="bold">{ex(title_display)}</text>
  <text x="320" y="195" font-family="monospace" font-size="10" fill="#a8a69e" text-anchor="middle">{ex(domain)}</text>
  <text x="320" y="350" font-family="monospace" font-size="9" fill="#c8c4bc" text-anchor="middle">{ex(url[:90])}</text>
</svg>""", encoding="utf-8")
    return svg_path.name


async def _safe_screenshot(url: str) -> str:
    """
    Wrapper used by gather_web_search. asyncio.gather with return_exceptions=True
    means any unhandled exception becomes an exception object in the results list,
    silently bypassing the isinstance(shot, str) check and leaving screenshot_path
    empty. This wrapper guarantees a string return and logs any unexpected failure.
    """
    try:
        return await capture_screenshot(url)
    except Exception as e:
        log.error("Unexpected screenshot error for %s: %s", url[:60], e, exc_info=True)
        return ""
    
# ══════════════════════════════════════════════════════════════════════════════
#  Deep Crawl
# ══════════════════════════════════════════════════════════════════════════════

def extract_links(html: str, base_url: str) -> list[str]:
    """Extract absolute href links from HTML."""
    links = re.findall(r'href=["\']([^"\']+)["\']', html)
    base = urlparse(base_url)
    out = []
    for l in links:
        if l.startswith("javascript:"): continue
        if l.startswith("#"): continue
        abs_url = urljoin(base_url, l)
        p = urlparse(abs_url)
        # stay on same domain
        if p.netloc == base.netloc and p.scheme in ("http","https"):
            out.append(abs_url)
    return list(dict.fromkeys(out))  # dedupe, preserve order


def html_to_text(html: str) -> str:
    """Very simple HTML → plain text."""
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>",  " ", text,  flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()[:8000]


async def deep_crawl_url(url: str, depth: int, breadth: int, timeout: float,
                         job_id: str = "", on_page: Optional[Callable] = None) -> str:
    """Fetch a URL and optionally crawl child links. Returns concatenated text.
    Calls on_page(url, text_chars) after each successful page fetch."""
    collected: list[str] = []
    visited: set[str] = set()

    async def fetch_one(u: str, remaining_depth: int):
        if u in visited or len(collected) > 20: return
        visited.add(u)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as c:
                r = await c.get(u, headers={"User-Agent":"Vera-Research/1.0"})
                html = r.text
            text = html_to_text(html)
            if text:
                collected.append(f"[{u}]\n{text[:3000]}")
                if on_page:
                    try: await on_page(u, len(text))
                    except Exception: pass
                if job_id:
                    from urllib.parse import urlparse
                    domain = urlparse(u).netloc
                    await broadcast(job_id, {
                        "type": "crawl_progress",
                        "url": u,
                        "domain": domain,
                        "chars": len(text),
                        "depth": depth - remaining_depth,
                    })
            if remaining_depth > 0:
                child_links = extract_links(html, u)[:breadth]
                await asyncio.gather(*[fetch_one(cl, remaining_depth-1) for cl in child_links],
                                     return_exceptions=True)
        except Exception as e:
            if job_id:
                await broadcast(job_id, {"type":"crawl_error","url":u,"error":str(e)[:80]})
            log.debug("crawl %s: %s", u, e)

    await fetch_one(url, depth)
    return "\n\n---\n\n".join(collected)


# ══════════════════════════════════════════════════════════════════════════════
#  Redis source
# ══════════════════════════════════════════════════════════════════════════════

async def query_redis(query: str) -> list[Citation]:
    src = next((s for s in sources if s.id == "redis" and s.enabled), None)
    if not src: return []
    try:
        import redis.asyncio as aioredis  # type: ignore
        r = aioredis.Redis(
            host=src.config.get("host","llm.int"),
            port=int(src.config.get("port",6379)),
            password=src.config.get("password") or None,
            db=int(src.config.get("db",0)),
            decode_responses=True,
        )
        prefix = src.config.get("prefix","vera:")
        # Simple key scan
        keys = []
        async for k in r.scan_iter(f"{prefix}*", count=100):
            keys.append(k)
            if len(keys) >= 20: break
        # Filter by query words
        query_words = set(query.lower().split())
        citations = []
        for k in keys:
            val = await r.get(k)
            if not val: continue
            if any(w in val.lower() for w in query_words if len(w) > 3):
                citations.append(Citation(
                    id=str(uuid.uuid4())[:8],
                    url=f"redis://{k}",
                    title=k,
                    snippet=val[:300],
                    source_type="redis",
                ))
        await r.aclose()
        return citations
    except ImportError:
        log.debug("redis package not installed")
        return []
    except Exception as e:
        log.warning("Redis query failed: %s", e)
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  Web search & source gathering
# ══════════════════════════════════════════════════════════════════════════════

async def search_searxng(query: str, limit: int) -> list[dict]:
    src = next((s for s in sources if s.id=="searxng" and s.enabled), None)
    if not src: return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(f"{src.config.get('host','http://llm.int:8888')}/search",
                params={"q":query,"format":"json","language":"en","safesearch":web_cfg.safe_search})
            return r.json().get("results",[])[:limit]
    except Exception as e:
        log.debug("searxng: %s", e); return []


async def search_brave(query: str, limit: int) -> list[dict]:
    src = next((s for s in sources if s.id=="brave" and s.enabled), None)
    if not src or not src.config.get("api_key"): return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get("https://api.search.brave.com/res/v1/web/search",
                params={"q":query,"count":limit},
                headers={"Accept":"application/json","X-Subscription-Token":src.config["api_key"]})
            return [{"url":w["url"],"title":w["title"],"content":w.get("description","")}
                    for w in r.json().get("web",{}).get("results",[])[:limit]]
    except Exception as e:
        log.debug("brave: %s", e); return []


def _clean_search_url(url: str) -> str:
    """
    Decode tracker/redirect wrapper URLs back to the real destination URL.

    Handles:
      DuckDuckGo  https://duckduckgo.com/l/?uddg=<encoded>&rut=...
      SearXNG     may pass through similar redirects
      HTML entity decoded URLs  (& → &amp; etc.)
    """
    import html as _html
    from urllib.parse import urlparse, parse_qs, unquote
    url = _html.unescape(url)          # &amp; → &, &#x2F; → / etc.
    parsed = urlparse(url)
    # DuckDuckGo redirect  /l/ or /l.php
    if parsed.netloc in ("duckduckgo.com","www.duckduckgo.com") and parsed.path.startswith("/l"):
        qs = parse_qs(parsed.query)
        target = qs.get("uddg", qs.get("u", [""]))[0]
        if target:
            return unquote(target)
    # Google AMP/redirect
    if "/url?" in url:
        qs = parse_qs(parsed.query)
        target = qs.get("url", qs.get("q", [""]))[0]
        if target:
            return unquote(target)
    # Bing redirect
    if parsed.netloc.endswith("bing.com") and parsed.path.startswith("/ck/"):
        qs = parse_qs(parsed.query)
        target = qs.get("u", [""])[0]
        if target:
            return unquote(target.lstrip("a1"))
    return url


async def search_ddg(query: str, limit: int) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as c:
            r = await c.get("https://html.duckduckgo.com/html/",
                params={"q":query}, headers={"User-Agent":"Vera-Research/1.0"})
        links    = re.findall(r'class="result__a"[^>]+href="([^"]+)"[^>]*>([^<]+)<', r.text)
        snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)<', r.text)
        results = []
        for i, (raw_url, title) in enumerate(links[:limit]):
            clean = _clean_search_url(raw_url)
            # Skip DDG internal pages and empty URLs
            if not clean or "duckduckgo.com" in clean:
                continue
            results.append({
                "url":     clean,
                "title":   title.strip(),
                "content": snippets[i] if i < len(snippets) else ""
            })
        return results
    except Exception as e:
        log.debug("ddg: %s", e); return []


async def gather_web_search(query: str, job_id: str) -> list[Citation]:
    limit = web_cfg.result_count
    engine = web_cfg.engine

    results: list[dict] = []
    if engine == "brave":
        results = await search_brave(query, limit)
    if not results and engine in ("searxng","auto"):
        results = await search_searxng(query, limit)
    if not results:
        results = await search_ddg(query, limit)

    citations: list[Citation] = []
    crawl_tasks, shot_tasks = [], []

    # Relevance filter: score each result against query terms
    query_terms = set(re.sub(r"[^a-z0-9 ]", " ", query.lower()).split()) - {
        "the","a","an","is","are","was","were","be","been","being",
        "have","has","had","do","does","did","will","would","could","should",
        "may","might","shall","can","need","dare","used","ought","of","in",
        "on","at","to","for","with","by","from","as","into","through","about",
        "what","how","why","when","where","who","which","that","this","these",
    }

    def _relevance(title: str, snippet: str) -> float:
        text = (title + " " + snippet).lower()
        if not query_terms: return 1.0
        hits = sum(1 for t in query_terms if t in text)
        return hits / len(query_terms)

    for item in results:
        url     = _clean_search_url(item.get("url",""))
        title   = item.get("title", url)
        snippet = item.get("content", item.get("snippet",""))[:400]
        # Skip obviously irrelevant results (less than 20% term overlap)
        if _relevance(title, snippet) < 0.2 and len(results) > 4:
            log.debug("Skipping low-relevance result: %s", title[:60])
            continue
        cit = Citation(id=str(uuid.uuid4())[:8], url=url, title=title,
                       snippet=snippet, source_type="web")
        citations.append(cit)
        shot_tasks.append(_safe_screenshot(url))
        # Always crawl at least depth 1 to get real page content
        depth = max(1, web_cfg.crawl_depth)
        _jid = job_id if isinstance(job_id, str) else ""
        crawl_tasks.append(deep_crawl_url(url, depth,
                                           web_cfg.crawl_breadth, web_cfg.crawl_timeout,
                                           job_id=_jid))

    shots, crawls = await asyncio.gather(
        asyncio.gather(*shot_tasks, return_exceptions=True),
        asyncio.gather(*crawl_tasks, return_exceptions=True),
    )
    for cit, shot, crawled in zip(citations, shots, crawls):
        if isinstance(shot, str): cit.screenshot_path = shot
        if isinstance(crawled, str) and crawled: cit.full_text = crawled

    return citations


async def gather_arxiv(query: str, limit: int = 5) -> list[Citation]:
    # Active if explicitly named "arxiv" OR if any enabled NEWS source is active
    if not (any(s.id=="arxiv" and s.enabled for s in sources) or
            any(s.type==SourceType.NEWS and s.enabled for s in sources)):
        return []
    log.debug("gather_arxiv: querying for %r", query[:60])
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get("https://export.arxiv.org/api/query",
                params={"search_query":f"all:{query}","max_results":limit,"sortBy":"relevance"})
        cits = []
        for entry in re.findall(r"<entry>(.*?)</entry>", r.text, re.S):
            tm = re.search(r"<title>(.*?)</title>", entry, re.S)
            sm = re.search(r"<summary>(.*?)</summary>", entry, re.S)
            im = re.search(r"<id>(.*?)</id>", entry)
            url = im.group(1).strip() if im else ""
            if url:
                cits.append(Citation(id=str(uuid.uuid4())[:8], url=url,
                    title=(tm.group(1).strip().replace("\n"," ") if tm else "arXiv"),
                    snippet=(sm.group(1).strip().replace("\n"," ")[:300] if sm else ""),
                    source_type="arxiv"))
        return cits
    except Exception as e:
        log.debug("arxiv: %s", e); return []


async def gather_hackernews(query: str, limit: int = 4) -> list[Citation]:
    # Active if explicitly named "hackernews" OR if any enabled NEWS source is active
    if not (any(s.id=="hackernews" and s.enabled for s in sources) or
            any(s.type==SourceType.NEWS and s.enabled for s in sources)):
        return []
    log.debug("gather_hackernews: querying for %r", query[:60])
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get("https://hn.algolia.com/api/v1/search",
                params={"query":query,"hitsPerPage":limit,"tags":"story"})
        return [Citation(id=str(uuid.uuid4())[:8],
            url=h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID','')}",
            title=h.get("title","HN Story"),
            snippet=f"Points:{h.get('points',0)} · Comments:{h.get('num_comments',0)}",
            source_type="hackernews") for h in r.json().get("hits",[])]
    except Exception as e:
        log.debug("hn: %s", e); return []




# ══════════════════════════════════════════════════════════════════════════════
#  Neo4j source
# ══════════════════════════════════════════════════════════════════════════════

def _neo4j_extract_cits(records, prop: str, uri: str) -> list:
    """Extract Citation objects from neo4j records regardless of driver type (sync or async)."""
    cits = []
    for record in records:
        try:
            # record.data() works on both sync and async neo4j records
            row = record.data() if hasattr(record, "data") else dict(record)
            # Find the first node-like object in the row values
            node: dict = {}
            for v in row.values():
                if v is None:
                    continue
                if hasattr(v, "keys") and hasattr(v, "get"):
                    try:
                        node = dict(v)
                        break
                    except Exception:
                        pass
                elif isinstance(v, dict):
                    node = v
                    break
            # Fall back: treat all scalar values as a flat dict
            if not node:
                node = {k: str(v) for k, v in row.items() if v is not None}
            text  = (node.get(prop) or node.get("text") or node.get("content")
                     or node.get("name") or str(node)[:400])
            title = (node.get("title") or node.get("name") or node.get("id")
                     or "Neo4j node")
            url   = (node.get("url") or node.get("uri")
                     or f"neo4j://{uri}/{str(node.get('id','?'))}")
            cits.append(Citation(
                id=str(uuid.uuid4())[:8], url=url, title=str(title)[:120],
                snippet=str(text)[:400], source_type="neo4j",
            ))
        except Exception as exc:
            log.debug("neo4j record parse error: %s", exc)
    return cits


def _neo4j_build_cypher(cypher: str, label: str, prop: str) -> tuple[str, str]:
    """Return (cypher_str, param_name) for the query to run."""
    if cypher:
        return cypher, "query"
    if label:
        return (
            f"MATCH (n:`{label}`) WHERE toLower(n.`{prop}`) CONTAINS toLower($q) RETURN n LIMIT 15",
            "q",
        )
    # Generic full-text scan — searches text/name/content/title properties
    return (
        "MATCH (n) WHERE "
        "toLower(coalesce(n.text,'')) CONTAINS toLower($q) OR "
        "toLower(coalesce(n.name,'')) CONTAINS toLower($q) OR "
        "toLower(coalesce(n.content,'')) CONTAINS toLower($q) OR "
        "toLower(coalesce(n.title,'')) CONTAINS toLower($q) "
        "RETURN n LIMIT 15",
        "q",
    )


async def _query_neo4j_via_vera_session(cypher_str: str, param_name: str,
                                        query: str, prop: str, uri: str) -> list[Citation]:
    """
    Try to run the Cypher against a live Vera session driver.
    Vera exposes its Neo4j driver at /api/sessions/active → vera.mem.graph._driver.
    Using the existing driver avoids opening a duplicate connection and works
    even when the bolt port is firewalled to local-only.
    Returns [] on any failure so the caller can fall back.
    """
    try:
        from Vera.ChatUI.api.session import sessions, get_or_create_vera  # type: ignore
        if not sessions:
            return []
        sid = sorted(sessions.keys(), reverse=True)[0]
        vera = get_or_create_vera(sid)
        drv  = vera.mem.graph._driver          # sync neo4j Driver
        with drv.session() as db_sess:
            result = db_sess.run(cypher_str, {param_name: query})
            records = list(result)
        cits = _neo4j_extract_cits(records, prop, uri)
        log.info("neo4j (via Vera session) returned %d results", len(cits))
        return cits
    except Exception as e:
        log.debug("neo4j via Vera session failed (%s), will try direct", e)
        return []


async def query_neo4j(query: str) -> list[Citation]:
    src = next((s for s in sources if s.id == "neo4j" and s.enabled), None)
    if not src: return []
    uri      = src.config.get("uri", "bolt://localhost:7687")
    user     = src.config.get("user", "neo4j")
    password = src.config.get("password", "")
    cypher   = src.config.get("cypher", "")
    label    = src.config.get("node_label", "")
    prop     = src.config.get("text_property", "text")

    cypher_str, param_name = _neo4j_build_cypher(cypher, label, prop)

    # ── Strategy 1: reuse the live Vera session driver (no extra connection) ──
    cits = await _query_neo4j_via_vera_session(cypher_str, param_name, query, prop, uri)
    if cits:
        return cits

    # ── Strategy 2: open a direct async connection ────────────────────────────
    try:
        from neo4j import AsyncGraphDatabase  # type: ignore
        drv = AsyncGraphDatabase.driver(uri, auth=(user, password))
        try:
            async with drv.session() as session:
                result = await session.run(cypher_str, {param_name: query})
                records = [r async for r in result]
            cits = _neo4j_extract_cits(records, prop, uri)
        finally:
            await drv.close()
        log.info("neo4j (direct async) returned %d results", len(cits))
        return cits
    except ImportError:
        log.warning("neo4j package not installed (pip install neo4j)")
        return []
    except Exception as e:
        log.warning("Neo4j query failed: %s", e)
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  ChromaDB source  (HTTP client OR local persistent directory)
# ══════════════════════════════════════════════════════════════════════════════

def _is_chroma_store(path: str) -> bool:
    """Return True if path looks like a ChromaDB PersistentClient store root."""
    import os as _os
    # Chroma v0.4+ stores: chroma.sqlite3 at root, or a 'data_level0.bin' / index files
    markers = ["chroma.sqlite3", "chroma-collections.parquet",
               "index", ".chroma"]
    return any(_os.path.exists(_os.path.join(path, m)) for m in markers)


def _find_chroma_stores(root: str) -> list[str]:
    """
    Given a root path, return all chroma store directories.
    If root itself is a store → [root].
    If root contains sub-directories that are stores → those sub-dirs.
    Recurses one level deep only (stores-of-stores not supported).
    """
    import os as _os
    if _is_chroma_store(root):
        return [root]
    # Scan immediate sub-directories
    stores = []
    try:
        for entry in sorted(_os.scandir(root), key=lambda e: e.name):
            if entry.is_dir() and _is_chroma_store(entry.path):
                stores.append(entry.path)
    except PermissionError:
        pass
    return stores or [root]   # fallback: try root even if no markers found


def _chroma_make_clients(src) -> list:
    """
    Return a list of (client, label) tuples to query.
    Supports:
      - HTTP server                          host + port
      - Single chroma store dir             directory = /path/to/store
      - Parent dir of multiple stores       directory = /path/to/parent   (auto-detected)
      - Comma-separated paths               directory = /path/a,/path/b
      - Glob patterns                       directory = /data/chroma*
    Falls back to Vera session chromadb client if nothing configured.
    """
    import chromadb  # type: ignore
    import glob as _glob, os as _os

    clients = []
    dir_val = src.config.get("directory", "").strip()
    host    = src.config.get("host", "localhost")
    port    = int(src.config.get("port", 8000))

    if dir_val:
        # Step 1: expand globs and comma-separated paths
        raw_paths = [p.strip() for p in dir_val.split(",") if p.strip()]
        candidate_roots: list[str] = []
        for p in raw_paths:
            globbed = _glob.glob(p)
            candidate_roots.extend(globbed if globbed else [p])

        # Step 2: for each root, find actual chroma stores (may be sub-dirs)
        all_store_paths: list[str] = []
        for root in candidate_roots:
            all_store_paths.extend(_find_chroma_stores(root))

        # Step 3: open a PersistentClient per store
        seen_paths: set[str] = set()
        for store_path in all_store_paths:
            real = _os.path.realpath(store_path)
            if real in seen_paths:
                continue
            seen_paths.add(real)
            try:
                client = chromadb.PersistentClient(path=store_path)
                label  = _os.path.basename(store_path.rstrip("/"))
                clients.append((client, f"local:{label}"))
                log.debug("chroma: PersistentClient at %s", store_path)
            except Exception as e:
                log.warning("chroma: cannot open store %s: %s", store_path, e)
    else:
        try:
            client = chromadb.HttpClient(host=host, port=port)
            clients.append((client, f"http:{host}:{port}"))
            log.debug("chroma: HttpClient at %s:%s", host, port)
        except Exception as e:
            log.warning("chroma: cannot create HttpClient %s:%s: %s", host, port, e)

    # Last resort: reuse the live Vera session chromadb instance
    if not clients:
        try:
            from Vera.ChatUI.api.session import sessions, get_or_create_vera  # type: ignore
            if sessions:
                sid  = sorted(sessions.keys(), reverse=True)[0]
                vera = get_or_create_vera(sid)
                client = vera.mem.vec
                clients.append((client, "vera-session"))
                log.debug("chroma: using Vera session vec client")
        except Exception as e:
            log.debug("chroma: Vera session vec fallback failed: %s", e)

    return clients


async def query_chroma(query: str) -> list[Citation]:
    src = next((s for s in sources if s.id == "chroma" and s.enabled), None)
    if not src: return []
    try:
        import chromadb  # type: ignore
        collection_filter = src.config.get("collection", "").strip()
        n_results = int(src.config.get("n_results", 8))
        max_cols  = int(src.config.get("max_collections", 10))

        clients = _chroma_make_clients(src)
        if not clients:
            log.warning("chroma: no usable client configured")
            return []

        cits = []
        for client, client_label in clients:
            try:
                if collection_filter:
                    col_names = [collection_filter]
                else:
                    all_cols  = client.list_collections()
                    col_names = [c.name for c in all_cols][:max_cols]

                log.debug("chroma(%s): searching %d collections for %r",
                          client_label, len(col_names), query[:60])

                for col_name in col_names:
                    try:
                        col   = client.get_collection(col_name)
                        count = col.count()
                        if count == 0:
                            log.debug("chroma: collection %s is empty, skipping", col_name)
                            continue
                        k = min(n_results, count)
                        results = col.query(query_texts=[query], n_results=k)
                        docs  = results.get("documents", [[]])[0]
                        metas = results.get("metadatas",  [[]])[0]
                        ids   = results.get("ids",         [[]])[0]
                        dists = results.get("distances",   [[]])[0]
                        for doc, meta, cid, dist in zip(docs, metas, ids, dists):
                            m     = meta or {}
                            url   = m.get("url") or m.get("source") or f"chroma://{client_label}/{col_name}/{cid}"
                            title = m.get("title") or m.get("name") or f"{col_name}/{cid[:40]}"
                            cits.append(Citation(
                                id=str(uuid.uuid4())[:8], url=url, title=str(title)[:120],
                                snippet=str(doc)[:400], source_type="chroma",
                            ))
                    except Exception as e:
                        log.debug("chroma(%s) collection %s: %s", client_label, col_name, e)

            except Exception as e:
                log.warning("chroma client %s failed: %s", client_label, e)

        log.info("chroma returned %d results total", len(cits))
        return cits
    except ImportError:
        log.warning("chromadb not installed (pip install chromadb)")
        return []
    except Exception as e:
        log.warning("Chroma query failed: %s", e)
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  GitHub source
# ══════════════════════════════════════════════════════════════════════════════

async def gather_github(query: str, limit: int = 8) -> list[Citation]:
    src = next((s for s in sources if s.id == "github" and s.enabled), None)
    if not src: return []
    token = src.config.get("token", "")
    if not token:
        log.warning("GitHub source enabled but no token configured")
        return []
    orgs    = src.config.get("orgs", "")       # comma-separated org names to scope search
    repos   = src.config.get("repos", "")      # comma-separated repo names  owner/repo
    search_code = src.config.get("search_code", False)

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    cits = []
    try:
        async with httpx.AsyncClient(timeout=12.0, headers=headers) as c:
            # Build query scope
            scope = ""
            if repos:
                scope = " ".join(f"repo:{r.strip()}" for r in repos.split(",") if r.strip())
            elif orgs:
                scope = " ".join(f"org:{o.strip()}" for o in orgs.split(",") if o.strip())

            # Search repositories
            repo_q = f"{query} {scope}".strip()
            r = await c.get("https://api.github.com/search/repositories",
                            params={"q": repo_q, "per_page": limit, "sort": "stars"})
            if r.status_code == 200:
                for item in r.json().get("items", [])[:limit//2]:
                    cits.append(Citation(
                        id=str(uuid.uuid4())[:8],
                        url=item["html_url"],
                        title=item.get("full_name", item["name"]),
                        snippet=(item.get("description") or "")[:300],
                        source_type="github",
                    ))
            elif r.status_code == 401:
                log.error("GitHub: 401 Unauthorized — check token")
                return []
            else:
                log.warning("GitHub repo search: %s", r.status_code)

            # Also search code if configured or repos specified
            if search_code or repos:
                code_q = f"{query} {scope}".strip()
                r2 = await c.get("https://api.github.com/search/code",
                                 params={"q": code_q, "per_page": limit})
                if r2.status_code == 200:
                    for item in r2.json().get("items", [])[:limit//2]:
                        url = item.get("html_url", "")
                        cits.append(Citation(
                            id=str(uuid.uuid4())[:8],
                            url=url,
                            title=f"{item.get('repository',{}).get('full_name','')}/{item.get('name','')}",
                            snippet=item.get("path", ""),
                            source_type="github",
                        ))

        log.info("github returned %d results", len(cits))
        return cits
    except Exception as e:
        log.warning("GitHub query failed: %s", e)
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  Web archive sources (Wayback Machine + Common Crawl)
# ══════════════════════════════════════════════════════════════════════════════

async def gather_archive(query: str, active: set) -> list[Citation]:
    """Query Wayback Machine CDX API and/or Common Crawl index."""
    cits = []

    if "wayback" in active and any(s.id == "wayback" and s.enabled for s in sources):
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                # CDX API: find recent snapshots containing the query terms
                r = await c.get("http://web.archive.org/cdx/search/cdx",
                    params={
                        "q": query, "output": "json", "limit": 5,
                        "fl": "original,timestamp,statuscode,mimetype",
                        "filter": "statuscode:200", "collapse": "urlkey",
                    })
                if r.status_code == 200:
                    rows = r.json()[1:]  # skip header row
                    for row in rows[:5]:
                        orig_url, ts = row[0], row[1]
                        wb_url = f"https://web.archive.org/web/{ts}/{orig_url}"
                        cits.append(Citation(
                            id=str(uuid.uuid4())[:8],
                            url=wb_url,
                            title=f"[Archive] {orig_url[:80]}",
                            snippet=f"Archived {ts[:8]} from {orig_url[:100]}",
                            source_type="web_archive",
                        ))
        except Exception as e:
            log.debug("wayback: %s", e)

    if "commoncrawl" in active and any(s.id == "commoncrawl" and s.enabled for s in sources):
        try:
            # Common Crawl Index API
            async with httpx.AsyncClient(timeout=12.0) as c:
                r = await c.get("https://index.commoncrawl.org/CC-MAIN-2024-10-index",
                    params={"url": f"*{query.replace(' ','*')}*", "output": "json", "limit": 4})
                for line in r.text.strip().splitlines()[:4]:
                    try:
                        obj = json.loads(line)
                        url = obj.get("url", "")
                        cits.append(Citation(
                            id=str(uuid.uuid4())[:8],
                            url=url,
                            title=f"[CommonCrawl] {url[:80]}",
                            snippet=obj.get("filename", "")[:200],
                            source_type="web_archive",
                        ))
                    except Exception:
                        pass
        except Exception as e:
            log.debug("commoncrawl: %s", e)

    return cits

async def gather_all_sources(query: str, job: ResearchJob) -> tuple[list[Citation], str]:
    active = set(job.sources)
    task_map: dict[str, asyncio.Task] = {}

    # Check both by explicit source ID (chips) AND by type (for user-added sources)
    def _src_active(ids: set, types: set = set()) -> bool:
        """True if any matching source ID is in active, or any enabled source of matching type."""
        if active & ids:
            return True
        if types:
            return any(s.type.value in types and s.enabled and s.id in active for s in sources)
        return False

    if _src_active({"searxng","brave","crawl4ai"}, {"web_search","web_crawl"}):
        task_map["web"] = asyncio.create_task(gather_web_search(query, job.id))
    if _src_active({"arxiv"}, {"news"}):
        task_map["arxiv"] = asyncio.create_task(gather_arxiv(query))
    if _src_active({"hackernews"}, {"news"}):
        task_map["hn"] = asyncio.create_task(gather_hackernews(query))
    if _src_active({"redis"}, {"redis"}):
        task_map["redis"] = asyncio.create_task(query_redis(query))
    if _src_active({"neo4j"}, {"neo4j"}):
        task_map["neo4j"] = asyncio.create_task(query_neo4j(query))
    if _src_active({"chroma"}, {"chroma"}):
        task_map["chroma"] = asyncio.create_task(query_chroma(query))
    if _src_active({"github"}, {"github"}):
        task_map["github"] = asyncio.create_task(gather_github(query))
    if _src_active({"wayback","commoncrawl"}, {"web_archive"}):
        task_map["archive"] = asyncio.create_task(gather_archive(query, active))

    all_cits: list[Citation] = []
    if task_map:
        results = await asyncio.gather(*task_map.values(), return_exceptions=True)
        for name, res in zip(task_map.keys(), results):
            if isinstance(res, list): all_cits.extend(res)
            else: log.warning("Source %s failed: %s", name, res)

    job.citations.extend(all_cits)

    if not all_cits:
        return all_cits, ""

    ctx_lines = ["## Retrieved Sources\n"]
    for i, c in enumerate(all_cits, 1):
        ctx_lines.append(f"[{i}] **{c.title}** ({c.domain})")
        if c.snippet: ctx_lines.append(f"    > {c.snippet[:280]}")
        if c.full_text: ctx_lines.append(f"    [crawled {len(c.full_text)} chars]\n    {c.full_text[:600]}")
        ctx_lines.append(f"    URL: {c.url}\n")

    return all_cits, "\n".join(ctx_lines)


# ══════════════════════════════════════════════════════════════════════════════
#  Ollama helpers
# ══════════════════════════════════════════════════════════════════════════════

async def get_instance(tier: ModelTier) -> Optional[OllamaInstance]:
    for inst in instances:
        if inst.tier == tier and inst.enabled: return inst
    for inst in instances:
        if inst.enabled: return inst
    return None


async def stream_ollama(
    inst: OllamaInstance,
    prompt: str,
    system: str = "",
    job_id: str = "",
    slot: Optional[AgentSlot] = None,
    timeout_secs: float = 300.0,
) -> AsyncIterator[str]:
    payload = {"model":inst.model,"prompt":prompt,"system":system,"stream":True,
               "options":{"num_ctx":inst.ctx_size}}
    to = httpx.Timeout(connect=5.0, read=timeout_secs, write=30.0, pool=5.0)
    async with httpx.AsyncClient(timeout=to) as client:
        try:
            async with client.stream("POST", inst.generate_url, json=payload) as resp:
                resp.raise_for_status()
                async for raw in resp.aiter_lines():
                    if cancel_flags.get(job_id): break
                    if not raw: continue
                    try: chunk = json.loads(raw)
                    except json.JSONDecodeError: continue
                    tok = chunk.get("response","")
                    if tok:
                        if slot: slot.tokens += 1
                        await broadcast(job_id, {"type":"token","text":tok,"tier":inst.tier})
                        yield tok
                    if chunk.get("done"): break
        except httpx.ConnectError as e:
            err = f"\n\n⚠ Cannot reach {inst.name} at {inst.base_url}: {e}"
            await broadcast(job_id, {"type":"error","text":err}); yield err
        except (httpx.ReadTimeout, asyncio.TimeoutError):
            err = f"\n\n⚠ {inst.name} timed out after {timeout_secs}s"
            await broadcast(job_id, {"type":"error","text":err}); yield err
        except Exception as e:
            err = f"\n\n⚠ {inst.name}: {e}"
            await broadcast(job_id, {"type":"error","text":err}); yield err


async def collect_ollama(
    inst: OllamaInstance,
    prompt: str,
    system: str = "",
    job_id: str = "",
    slot: Optional[AgentSlot] = None,
    timeout_secs: float = 300.0,
) -> str:
    """Non-streaming helper for internal pipeline steps."""
    parts: list[str] = []
    async for tok in stream_ollama(inst, prompt, system, job_id, slot, timeout_secs):
        parts.append(tok)
        if cancel_flags.get(job_id): break
    return "".join(parts)


async def list_models(inst: OllamaInstance) -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(inst.tags_url)
            return [m["name"] for m in r.json().get("models",[])]
    except Exception: return []


# ══════════════════════════════════════════════════════════════════════════════
#  Broadcast
# ══════════════════════════════════════════════════════════════════════════════

async def broadcast(job_id: str, payload: dict):
    msg = json.dumps(payload)
    for ws in list(ws_clients.get(job_id, [])):
        try: await ws.send_text(msg)
        except Exception:
            try: ws_clients[job_id].remove(ws)
            except ValueError: pass


# ══════════════════════════════════════════════════════════════════════════════
#  File-tree output
# ══════════════════════════════════════════════════════════════════════════════

def parse_file_tree(raw: str) -> dict[str, str]:
    """
    Parse LLM output that looks like:
        === FILE: path/to/file.ext ===
        <content>
        === END ===
    Returns {path: content}
    """
    files: dict[str, str] = {}
    pattern = re.compile(r"===\s*FILE:\s*([^\s=]+)\s*===\s*(.*?)===\s*END\s*===", re.S)
    for m in pattern.finditer(raw):
        path    = m.group(1).strip()
        content = m.group(2).strip()
        files[path] = content

    # Also handle markdown fenced blocks with filenames
    # ```python  # path/to/file.py
    md_pattern = re.compile(r"```[a-z]*\s*#\s*([^\n]+)\n(.*?)```", re.S)
    for m in md_pattern.finditer(raw):
        path = m.group(1).strip()
        content = m.group(2).strip()
        if "/" in path or "." in path:
            files[path] = content

    return files


async def materialise_file_tree(job: ResearchJob, project: Optional[Project] = None):
    """Write parsed file tree to disk under projects/<id>/files/"""
    tree = job.file_tree
    if not tree: return

    if project:
        base = PROJECTS_DIR / project.id / "files"
    else:
        base = PROJECTS_DIR / "standalone" / job.id / "files"
    base.mkdir(parents=True, exist_ok=True)

    # Also write source crawl content as _sources/ files if available
    if hasattr(job, "citations") and job.citations:
        for i, cit in enumerate(job.citations[:10]):
            if cit.full_text and len(cit.full_text) > 200:
                from urllib.parse import urlparse
                domain = urlparse(cit.url).netloc.replace(".", "_")
                src_path = base / "_sources" / f"{i+1}_{domain}.txt"
                src_path.parent.mkdir(parents=True, exist_ok=True)
                src_path.write_text(
                    f"Source: {cit.url}\nTitle: {cit.title}\n\n{cit.full_text}",
                    encoding="utf-8"
                )
                # Track in file_tree
                rel = str(src_path.relative_to(base))
                if rel not in tree:
                    tree[f"_sources/{i+1}_{domain}.txt"] = cit.full_text[:500]
                await broadcast(job.id, {"type":"file_created",
                                          "path":f"_sources/{i+1}_{domain}.txt"})

    for rel_path, content in tree.items():
        # Sanitise path
        safe = Path(rel_path)
        if safe.is_absolute(): safe = Path(*safe.parts[1:])
        target = base / safe
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    await broadcast(job.id, {"type":"file_tree","files":list(tree.keys()),"base":str(base)})


# ══════════════════════════════════════════════════════════════════════════════
#  Project / Content-Base context
# ══════════════════════════════════════════════════════════════════════════════

async def update_project_context(project: Project, job: ResearchJob, thinker: Optional[OllamaInstance]):
    """After each round, update the rolling context summary and file tree."""
    project.rounds.append(ProjectRound(
        id=str(uuid.uuid4())[:8],
        job_id=job.id,
        round_num=len(project.rounds)+1,
        query=job.query,
        result=job.result or "",
        citations=[c.to_dict_full() for c in job.citations],
    ))
    if job.file_tree:
        project.file_tree.update(job.file_tree)

    # Summarise context with thinker if available
    if thinker and len(project.rounds) > 1:
        existing = project.context_summary
        new_content = (job.result or "")[:3000]
        summary_prompt = (
            f"Existing project context summary:\n{existing}\n\n"
            f"New round (query: {job.query}):\n{new_content}\n\n"
            "Update the summary to incorporate the new round. "
            "Keep it under 800 words. Focus on: what has been covered, "
            "key facts established, files created, open questions."
        )
        summary_sys = "You are a research project manager. Maintain a concise rolling summary."
        try:
            project.context_summary = await asyncio.wait_for(
                collect_ollama(thinker, summary_prompt, summary_sys, timeout_secs=SUMMARY_TIMEOUT),
                timeout=SUMMARY_TIMEOUT + 10
            )
        except asyncio.TimeoutError:
            project.context_summary = existing + f"\n\n[Round {len(project.rounds)}]: {job.query}"
    elif not project.context_summary:
        project.context_summary = (
            f"Project: {project.name}\n"
            f"Round 1 query: {job.query}\n"
            f"Summary: {(job.result or '')[:600]}"
        )

    project.updated_at = time.time()
    # Persist to disk
    proj_file = PROJECTS_DIR / project.id / "project.json"
    proj_file.parent.mkdir(exist_ok=True)
    proj_data = {
        **project.to_dict(),
        "context_summary": project.context_summary,
        "file_tree_keys": list(project.file_tree.keys()),
        "rounds": [{"id":r.id,"round_num":r.round_num,"query":r.query,
                    "created_at":r.created_at} for r in project.rounds],
    }
    proj_file.write_text(json.dumps(proj_data, indent=2), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
#  Pipeline helpers
# ══════════════════════════════════════════════════════════════════════════════

WRITE_SYS = (
    "You are a research writer. Produce clear, thorough, well-structured reports in Markdown. "
    "Use ## headers, bullet points, and **bold** for key terms. "
    "When sources are provided cite them inline as [1], [2] etc. "
    "End with a ## References section."
)

GUIDE_SYS = (
    "You are a technical writer producing comprehensive guides. "
    "Write in depth, using ## and ### headers, numbered steps, code blocks where relevant. "
    "This is one section of a larger guide — be thorough and complete for your assigned section. "
    "Cite sources inline as [1], [2] etc."
)

FILESTORE_SYS = (
    "You are a senior software engineer. Produce complete, working files. "
    "For EVERY file you create, wrap it exactly like this:\n\n"
    "=== FILE: path/to/filename.ext ===\n"
    "<complete file contents>\n"
    "=== END ===\n\n"
    "Include ALL files needed: configs, dockerfiles, scripts, READMEs, etc. "
    "Do not truncate or abbreviate. Every file must be production-ready."
)

# ── Coding mode system prompts ────────────────────────────────────────────────

CODE_ARCH_SYS = (
    "You are a software architect. Given a task and research context, produce a "
    "detailed architecture plan. Be precise and specific — no vague descriptions.\n\n"
    "Your output MUST be valid JSON matching this schema:\n"
    "{\n"
    '  "overview": "One paragraph describing what is being built",\n'
    '  "stack": ["tech1", "tech2"],\n'
    '  "files": [\n'
    '    {"path": "relative/path/file.ext", "purpose": "what this file does", '
    '"depends_on": ["other/file.ext"]}\n'
    "  ],\n"
    '  "interfaces": [\n'
    '    {"name": "InterfaceName", "description": "what it defines"}\n'
    "  ],\n"
    '  "implementation_order": ["file1.ext", "file2.ext"],\n'
    '  "notes": "Any important constraints or patterns to follow"\n'
    "}\n\n"
    "Respond with ONLY the JSON — no preamble, no markdown fences."
)

CODE_IMPL_SYS = (
    "You are a senior software engineer implementing specific files.\n\n"
    "Rules:\n"
    "- Write COMPLETE, working code — never use placeholders like '# TODO' or '...'\n"
    "- Every file must be immediately runnable/importable\n"
    "- Follow the architecture plan and interface definitions exactly\n"
    "- Be consistent with files already written\n"
    "- Wrap each file like this:\n\n"
    "=== FILE: path/to/file.ext ===\n"
    "<complete contents>\n"
    "=== END ===\n\n"
    "Write ONLY the file content — no explanations between files."
)

CODE_REVIEW_SYS = (
    "You are a code reviewer. Review the implemented files for:\n"
    "1. Correctness — will this actually run?\n"
    "2. Completeness — are all imports present, all functions implemented?\n"
    "3. Consistency — does it match the architecture and other files?\n"
    "4. Security — obvious vulnerabilities?\n\n"
    "Respond ONLY with valid JSON:\n"
    "{\n"
    '  "verdict": "pass" | "patch",\n'
    '  "issues": [\n'
    '    {"file": "path/to/file.ext", "line_hint": "approx location", '
    '"severity": "error"|"warning", "description": "what is wrong", '
    '"fix": "exact corrected code"}\n'
    "  ],\n"
    '  "summary": "brief overall assessment"\n'
    "}\n\n"
    "If verdict is 'pass', issues array must be empty.\n"
    "Respond with ONLY the JSON — no preamble."
)

CODE_CONTINUITY_SYS = (
    "You are a technical project manager. Summarise the current state of a "
    "coding project so a fresh context window can continue it coherently.\n\n"
    "Respond ONLY with valid JSON:\n"
    "{\n"
    '  "summary": "What has been built, key design decisions made",\n'
    '  "files_done": ["list of completed file paths"],\n'
    '  "files_pending": ["list of files still to implement"],\n'
    '  "key_interfaces": "Critical interfaces/types/contracts already defined",\n'
    '  "continuation_notes": "What the next run must know to continue correctly"\n'
    "}\n\n"
    "Respond with ONLY the JSON."
)


# ══════════════════════════════════════════════════════════════════════════════
#  Coding pipeline
# ══════════════════════════════════════════════════════════════════════════════

# How many tokens of written code to include in continuation context
CODE_CONTEXT_WINDOW  = 6000   # chars of recent code kept in prompt
# Max files per run before we emit a continuation signal
MAX_FILES_PER_RUN    = 8


def _recent_code_ctx(chain: ChainContext, chars: int = CODE_CONTEXT_WINDOW) -> str:
    """Return the tail of accumulated code for context injection."""
    if not chain.accumulated_code:
        return ""
    parts = []
    for path, content in list(chain.accumulated_code.items())[-6:]:
        parts.append(f"=== FILE: {path} ===\n{content[:800]}\n=== END ===")
    joined = "\n\n".join(parts)
    return joined[-chars:]


async def run_code_pipeline(job: ResearchJob, project: Optional[Project] = None) -> None:
    """
    Full coding pipeline.  Works for both first runs (chain_ctx is None)
    and continuation runs (chain_ctx already populated).

    Phases:
      1. Research  — gather sources (first run only, or if explicitly requested)
      2. Architect — thinker plans file tree + interfaces (first run only)
      3. Implement — writer generates files one at a time, analyst reviews each
      4. Continuity — thinker summarises state if files remain (emits chain signal)
    """
    thinker = await get_instance(ModelTier.THINKER)
    writer  = await get_instance(ModelTier.WRITER)
    analyst = await get_instance(ModelTier.ANALYST)

    if not writer and not thinker:
        job.status = JobStatus.ERROR
        job.error  = "No Ollama instance available"
        return

    use_writer = writer or thinker
    slot_t = slot_for(ModelTier.THINKER)
    slot_w = slot_for(ModelTier.WRITER)
    slot_a = slot_for(ModelTier.ANALYST)

    chain = job.chain_ctx

    # ── Phase 1: Research (first run only) ───────────────────────────────────
    research_ctx = ""
    if chain is None or not chain.architecture:
        if any(s in job.sources for s in ("searxng","brave","crawl4ai","arxiv","hackernews")):
            _, research_ctx = await _search_phase(job)
            if chain:
                chain.research_context = research_ctx
        else:
            await step_emit(job, "Research", "No search sources active — using model knowledge")

    if chain:
        research_ctx = chain.research_context or research_ctx

    # ── Phase 2: Architecture (first run only) ───────────────────────────────
    arch_plan: dict = {}

    if chain is None or not chain.architecture:
        use_arch = thinker or writer
        slot_on(slot_t, use_arch, job.id, "thinking")
        job.status = JobStatus.ARCHITECTING
        await step_emit(job, "Architecting", f"{use_arch.name} designing system…")

        arch_prompt = (
            f"Task: {job.query}\n\n"
            f"Research context:\n{research_ctx[:4000]}\n\n"
            "Produce a complete architecture plan as specified. "
            "Think carefully about the full file structure needed."
        )

        arch_raw = await collect_ollama(
            use_arch, arch_prompt, CODE_ARCH_SYS, job.id, slot_t,
            timeout_secs=THINKER_PLAN_TIMEOUT
        )
        slot_off(slot_t)

        # Parse architecture JSON
        try:
            # Strip any accidental markdown fences
            clean = re.sub(r"^```[a-z]*\s*|\s*```$", "", arch_raw.strip(), flags=re.M)
            arch_plan = json.loads(clean)
        except Exception as e:
            log.warning("Architecture JSON parse failed: %s — attempting extraction", e)
            try:
                start = arch_raw.index("{")
                end   = arch_raw.rindex("}") + 1
                arch_plan = json.loads(arch_raw[start:end])
            except Exception:
                # Fallback: treat as free-form, extract files
                arch_plan = {
                    "overview": arch_raw[:500],
                    "files": [],
                    "implementation_order": [],
                    "notes": arch_raw,
                }

        # Extract ordered file list
        impl_order  = arch_plan.get("implementation_order", [])
        all_files   = [f["path"] for f in arch_plan.get("files", [])]
        # Merge: impl_order first, then any not listed
        ordered_files = impl_order + [f for f in all_files if f not in impl_order]

        if not ordered_files:
            # Fallback if arch returned nothing useful
            ordered_files = ["main.py", "README.md"]

        # Initialise chain context
        chain = ChainContext(
            chain_id      = str(uuid.uuid4())[:12],
            run_number    = 1,
            original_task = job.query,
            architecture  = json.dumps(arch_plan, indent=2),
            files_planned = ordered_files,
            files_done    = [],
            files_pending = list(ordered_files),
            research_context = research_ctx,
        )
        job.chain_ctx = chain

        # Broadcast architecture to frontend
        await broadcast(job.id, {
            "type":  "architecture",
            "plan":  arch_plan,
            "files": ordered_files,
            "chain_id": chain.chain_id,
        })
        await step_emit(job, "Architecture", f"{len(ordered_files)} files planned")

    else:
        # Continuation run — resume from where we left off
        await step_emit(job, "Continuing",
            f"Run {chain.run_number} · {len(chain.files_done)} done · {len(chain.files_pending)} remaining")

    if cancel_flags.get(job.id):
        return

    # ── Phase 3: Implement files ─────────────────────────────────────────────
    job.status = JobStatus.CODING
    files_this_run = 0
    all_output_parts: list[str] = []

    while chain.files_pending and files_this_run < MAX_FILES_PER_RUN:
        if cancel_flags.get(job.id):
            break

        target_file = chain.files_pending[0]
        await step_emit(job, f"Coding {files_this_run+1}", target_file)
        slot_on(slot_w, use_writer, job.id, "writing")

        # Build a focused context: arch plan + interfaces + recent code
        recent_ctx = _recent_code_ctx(chain)
        file_info  = next(
            (f for f in json.loads(chain.architecture).get("files",[])
             if f["path"] == target_file),
            {"path": target_file, "purpose": "", "depends_on": []}
        )
        # Include contents of files this one depends on
        deps_ctx = ""
        for dep in file_info.get("depends_on", [])[:3]:
            if dep in chain.accumulated_code:
                deps_ctx += f"\n--- {dep} (dependency) ---\n{chain.accumulated_code[dep][:600]}\n"

        impl_prompt = (
            f"Original task: {chain.original_task}\n\n"
            f"Architecture overview:\n{json.loads(chain.architecture).get('overview','')}\n"
            f"Architecture notes:\n{json.loads(chain.architecture).get('notes','')}\n\n"
            f"File to implement: {target_file}\n"
            f"Purpose: {file_info.get('purpose','')}\n"
            f"Depends on: {', '.join(file_info.get('depends_on',[]))}\n\n"
            f"Files already completed: {', '.join(chain.files_done) or 'none yet'}\n"
            f"Files still pending after this: {', '.join(chain.files_pending[1:MAX_FILES_PER_RUN])}\n\n"
            f"{deps_ctx}"
            f"Recent code written (for consistency):\n{recent_ctx}\n\n"
            f"Implement {target_file} completely and correctly."
        )

        impl_parts: list[str] = []
        async for tok in stream_ollama(
            use_writer, impl_prompt, CODE_IMPL_SYS, job.id, slot_w,
            timeout_secs=WRITER_TIMEOUT
        ):
            impl_parts.append(tok)
            if cancel_flags.get(job.id): break

        slot_off(slot_w)
        raw_impl = "".join(impl_parts)
        all_output_parts.append(raw_impl)

        # Parse and store file
        parsed = parse_file_tree(raw_impl)
        if not parsed:
            # LLM forgot the wrapper — store as-is under target path
            parsed = {target_file: raw_impl.strip()}

        for path, content in parsed.items():
            chain.accumulated_code[path] = content
            job.file_tree[path] = content
            await broadcast(job.id, {"type":"file_created","path":path})

        # ── Analyst review of this file ──────────────────────────────────
        if analyst and not cancel_flags.get(job.id):
            job.status = JobStatus.REVIEWING
            slot_on(slot_a, analyst, job.id, "verifying")
            await step_emit(job, "Reviewing", target_file)

            review_prompt = (
                f"Architecture:\n{json.loads(chain.architecture).get('overview','')}\n\n"
                f"File being reviewed: {target_file}\n\n"
                f"Implementation:\n{raw_impl[:5000]}\n\n"
                f"Other files already written (for consistency check):\n{recent_ctx[:2000]}"
            )

            review_raw = ""
            try:
                review_raw = await asyncio.wait_for(
                    collect_ollama(analyst, review_prompt, CODE_REVIEW_SYS,
                                   job.id, slot_a, timeout_secs=ANALYST_TIMEOUT),
                    timeout=ANALYST_TIMEOUT + 10
                )
            except asyncio.TimeoutError:
                await step_emit(job, "Review timeout", f"Skipping review for {target_file}")

            slot_off(slot_a)

            if review_raw:
                try:
                    clean_r = re.sub(r"^```[a-z]*\s*|\s*```$", "", review_raw.strip(), flags=re.M)
                    review  = json.loads(clean_r)
                except Exception:
                    try:
                        s = review_raw.index("{"); e2 = review_raw.rindex("}")+1
                        review = json.loads(review_raw[s:e2])
                    except Exception:
                        review = {"verdict":"pass","issues":[],"summary":"parse error"}

                verdict = review.get("verdict","pass")
                issues  = review.get("issues",[])
                summary = review.get("summary","")

                await broadcast(job.id, {
                    "type":    "review",
                    "file":    target_file,
                    "verdict": verdict,
                    "issues":  issues,
                    "summary": summary,
                })
                await step_emit(job, f"Review: {verdict}", summary[:60] if summary else target_file)

                # If issues found, ask writer to patch
                if verdict == "patch" and issues and not cancel_flags.get(job.id):
                    job.status = JobStatus.CODING
                    slot_on(slot_w, use_writer, job.id, "writing")
                    await step_emit(job, "Patching", f"{len(issues)} issues in {target_file}")

                    issues_text = "\n".join(
                        f"- [{i['severity']}] {i['description']}\n  Fix: {i['fix']}"
                        for i in issues[:5]
                    )
                    patch_prompt = (
                        f"File: {target_file}\n\n"
                        f"Current implementation:\n{raw_impl[:4000]}\n\n"
                        f"Issues to fix:\n{issues_text}\n\n"
                        f"Produce the corrected complete file."
                    )
                    patch_parts: list[str] = []
                    async for tok in stream_ollama(
                        use_writer, patch_prompt, CODE_IMPL_SYS, job.id, slot_w,
                        timeout_secs=WRITER_TIMEOUT
                    ):
                        patch_parts.append(tok)
                        if cancel_flags.get(job.id): break

                    slot_off(slot_w)
                    patched = "".join(patch_parts)
                    all_output_parts.append(patched)

                    patched_tree = parse_file_tree(patched)
                    if not patched_tree:
                        patched_tree = {target_file: patched.strip()}
                    for path, content in patched_tree.items():
                        chain.accumulated_code[path] = content
                        job.file_tree[path] = content

        # Mark file done
        chain.files_pending.remove(target_file)
        chain.files_done.append(target_file)
        files_this_run += 1
        job.status = JobStatus.CODING

        # Materialise to disk
        if project:
            await materialise_file_tree(job, project)
        else:
            await materialise_file_tree(job, None)

    # ── Phase 4: Continuity / completion ─────────────────────────────────────

    if chain.files_pending and not cancel_flags.get(job.id):
        # More files remain — generate a continuity summary and signal continuation
        job.status = JobStatus.CHAINING
        await step_emit(job, "Chain summary",
            f"{len(chain.files_done)} done · {len(chain.files_pending)} remain · summarising…")

        use_sum = thinker or writer
        slot_on(slot_t, use_sum, job.id, "thinking")

        sum_prompt = (
            f"Original task: {chain.original_task}\n\n"
            f"Architecture:\n{chain.architecture[:2000]}\n\n"
            f"Files completed this run: {', '.join(chain.files_done[-files_this_run:])}\n"
            f"All files done: {', '.join(chain.files_done)}\n"
            f"Files still pending: {', '.join(chain.files_pending)}\n\n"
            f"Key interfaces/types defined so far:\n{_recent_code_ctx(chain, 2000)}\n\n"
            "Produce a continuity summary so the next run can continue correctly."
        )

        sum_raw = await collect_ollama(
            use_sum, sum_prompt, CODE_CONTINUITY_SYS, job.id, slot_t,
            timeout_secs=SUMMARY_TIMEOUT
        )
        slot_off(slot_t)

        try:
            clean_s = re.sub(r"^```[a-z]*\s*|\s*```$", "", sum_raw.strip(), flags=re.M)
            sum_data = json.loads(clean_s)
        except Exception:
            sum_data = {"summary": sum_raw[:800], "continuation_notes": "Continue from where left off."}

        chain.continuity_summary = sum_data.get("summary","")
        chain.run_number += 1
        chain.is_complete = False
        job.chain_continues = True

        await broadcast(job.id, {
            "type":        "chain_continue",
            "chain_id":    chain.chain_id,
            "run_number":  chain.run_number,
            "files_done":  chain.files_done,
            "files_pending": chain.files_pending,
            "summary":     chain.continuity_summary,
            "continuation_notes": sum_data.get("continuation_notes",""),
        })
        await step_emit(job, "⛓ Continue", f"Run {chain.run_number} ready when you trigger it")

    else:
        # All done
        chain.is_complete = True
        job.chain_continues = False

        # Generate README summary
        readme = (
            f"# {chain.original_task}\n\n"
            f"## Overview\n\n{json.loads(chain.architecture).get('overview','')}\n\n"
            f"## Stack\n\n"
            + "\n".join(f"- {s}" for s in json.loads(chain.architecture).get("stack",[]))
            + f"\n\n## Files\n\n"
            + "\n".join(f"- `{p}`" for p in chain.files_done)
            + f"\n\n## Notes\n\n{json.loads(chain.architecture).get('notes','')}\n"
        )
        if "README.md" not in chain.accumulated_code:
            chain.accumulated_code["README.md"] = readme
            job.file_tree["README.md"] = readme
            await broadcast(job.id, {"type":"file_created","path":"README.md"})

        await step_emit(job, "Complete",
            f"All {len(chain.files_done)} files written · {len(chain.accumulated_code)} in tree")

    # Build result string (manifest + recent output)
    job.result = (
        f"# Code generation: {chain.original_task}\n\n"
        f"**Run {chain.run_number - (0 if chain.is_complete else 1)} of chain `{chain.chain_id}`**\n\n"
        f"## Files written this run\n\n"
        + "\n".join(f"- `{f}`" for f in chain.files_done[-files_this_run:])
        + f"\n\n## Progress\n\n{len(chain.files_done)}/{len(chain.files_planned)} files done\n\n"
        + ("✅ **Complete**" if chain.is_complete
           else f"⛓ **{len(chain.files_pending)} files remaining** — trigger another run to continue")
        + "\n\n---\n\n"
        + "\n\n".join(all_output_parts)[-8000:]  # last 8k chars of generated code
    )


async def step_emit(job: ResearchJob, label: str, detail: str = ""):
    s = {"t":time.time(),"label":label,"detail":detail}
    job.steps.append(s)
    await broadcast(job.id, {"type":"step",**s})


def slot_for(tier: ModelTier) -> Optional[AgentSlot]:
    return next((s for s in agent_slots if s.tier == tier), None)


def slot_on(slot: Optional[AgentSlot], inst: OllamaInstance, job_id: str, status: str):
    if not slot: return
    slot.job_id = job_id; slot.status = status
    slot.model  = inst.model; slot.started_at = time.time()


def slot_off(slot: Optional[AgentSlot]):
    if not slot: return
    slot.status = "idle"; slot.job_id = None


async def _search_phase(job: ResearchJob) -> tuple[list[Citation], str]:
    job.status = JobStatus.SEARCHING
    await step_emit(job, "Searching", "Gathering sources…")
    cits, ctx = await gather_all_sources(job.query, job)
    await broadcast(job.id, {"type":"citations","citations":[c.to_dict() for c in cits]})
    if cits: await step_emit(job, "Sources", f"{len(cits)} found")
    return cits, ctx


# ══════════════════════════════════════════════════════════════════════════════
#  Analyst with timeout (fixes stuck analyser)
# ══════════════════════════════════════════════════════════════════════════════

ANALYST_TIMEOUT      = 600.0   # analyst verification max seconds
THINKER_PLAN_TIMEOUT = 600.0   # planning/decompose/outline steps (JSON responses)
THINKER_THINK_TIMEOUT= 600.0   # deep reasoning/synthesis steps (long prose)
WRITER_TIMEOUT       = 300.0   # writer section/extraction steps
SUMMARY_TIMEOUT      = 300.0   # rolling context summary update

async def run_analyst_phase(job: ResearchJob, draft: str,
                             analyst: OllamaInstance, slot_a: Optional[AgentSlot]) -> str:
    """Run analyst verification with a hard timeout so it can't block forever."""
    slot_on(slot_a, analyst, job.id, "verifying")
    job.status = JobStatus.VERIFYING
    await step_emit(job, "Verifying", f"{analyst.name} cross-checking (max {int(ANALYST_TIMEOUT)}s)…")

    verify_sys = (
        "You are a critical research analyst. Review the draft for accuracy, completeness, "
        "and logical consistency. Append a brief ## Verification note at the end. "
        "Do NOT rewrite the entire document — only append your notes."
    )
    verify_prompt = f"Query: {job.query}\n\nDraft:\n{draft[:6000]}"

    try:
        result = await asyncio.wait_for(
            collect_ollama(analyst, verify_prompt, verify_sys,
                           job.id, slot_a, timeout_secs=ANALYST_TIMEOUT),
            timeout=ANALYST_TIMEOUT + 10
        )
        slot_off(slot_a)
        return result or draft
    except asyncio.TimeoutError:
        slot_off(slot_a)
        await step_emit(job, "Verify timeout", f"Skipped after {int(ANALYST_TIMEOUT)}s")
        return draft + "\n\n---\n*Analyst verification timed out.*"


# ══════════════════════════════════════════════════════════════════════════════
#  Guide / multi-section output
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
#  Recursive Research Engine
#  ─────────────────────────
#  Instead of one search → one write, the engine:
#    1. Plans a tree of questions (breadth-first per level)
#    2. For each question: searches, reads full page text, identifies
#       further sub-questions the sources raise ("what I still don't know")
#    3. Recurses up to max_depth levels, gathering citations at every level
#    4. Builds a knowledge base across all levels
#    5. Synthesises into a final document
#
#  This turns it from a "summarise the top 8 search results" tool into
#  something that actually follows the research thread.
# ══════════════════════════════════════════════════════════════════════════════

MAX_RECURSIVE_DEPTH   = 3     # levels deep
MAX_QUESTIONS_PER_LEVEL = 4   # sub-questions per node
MAX_TOTAL_QUESTIONS   = 16    # circuit-breaker


@dataclass
class ResearchNode:
    question: str
    depth: int
    parent: Optional[str] = None
    citations: list[Citation] = field(default_factory=list)
    findings: str = ""
    sub_questions: list[str] = field(default_factory=list)


async def research_node(
    node: ResearchNode,
    job: ResearchJob,
    thinker: Optional[OllamaInstance],
    writer: OllamaInstance,
    all_citations: list[Citation],
    knowledge_base: list[str],
) -> None:
    """
    Research one question node:
      1. Search for it
      2. Deep-crawl top results
      3. Extract key findings
      4. Identify follow-up questions (returned in node.sub_questions)
    """
    if cancel_flags.get(job.id): return

    depth_label = "·" * node.depth
    await step_emit(job, f"{depth_label} Research", node.question[:70])

    # Search
    cits, ctx = await gather_all_sources(node.question, job)
    node.citations = cits
    all_citations.extend(cits)
    # Broadcast the full accumulated citation list so the UI shows all sources found so far,
    # not just this node's results (which would wipe the previous node's citations).
    await broadcast(job.id, {"type":"citations","citations":[c.to_dict() for c in all_citations]})

    if not ctx and not cits:
        node.findings = f"No sources found for: {node.question}"
        return

    # Extract findings from this node's sources
    extract_sys = (
        "You are a research analyst extracting precise knowledge from sources. "
        "Be specific, cite facts, note contradictions, identify what is well-established "
        "vs uncertain. Do NOT write an introduction or conclusion — just dense findings."
    )
    extract_prompt = (
        f"Research question: {node.question}\n\n"
        f"Depth level: {node.depth} (0=root, higher=more specific)\n\n"
        f"Sources:\n{ctx[:8000]}\n\n"
        f"Prior knowledge base:\n{chr(10).join(knowledge_base[-4:]) if knowledge_base else 'None yet'}\n\n"
        "Extract ALL specific findings relevant to the question. "
        "Include: facts, numbers, dates, names, mechanisms, disagreements, caveats."
    )

    use_inst = writer  # fast extraction; thinker used for planning
    findings_parts: list[str] = []
    async for tok in stream_ollama(use_inst, extract_prompt, extract_sys, job.id, timeout_secs=WRITER_TIMEOUT):
        findings_parts.append(tok)
        if cancel_flags.get(job.id): break
    node.findings = "".join(findings_parts)

    # Identify sub-questions (only if we have depth budget)
    if node.depth < MAX_RECURSIVE_DEPTH:
        sub_sys = (
            "You identify precise follow-up research questions. "
            "Return ONLY a JSON array of strings. No other text."
        )
        sub_prompt = (
            f"Original question: {node.question}\n\n"
            f"Findings so far:\n{node.findings[:3000]}\n\n"
            f"What specific sub-questions do these findings raise that we should "
            f"investigate further? These should be specific, answerable questions "
            f"not yet covered. Return {MAX_QUESTIONS_PER_LEVEL} questions as a JSON array."
        )
        plan_inst = thinker or writer
        raw = await collect_ollama(plan_inst, sub_prompt, sub_sys, job.id, timeout_secs=THINKER_PLAN_TIMEOUT)
        try:
            qs = json.loads(raw[raw.index("["):raw.rindex("]")+1])
            node.sub_questions = [str(q) for q in qs[:MAX_QUESTIONS_PER_LEVEL]]
        except Exception:
            node.sub_questions = []

    # Add to knowledge base
    knowledge_base.append(
        f"[Level {node.depth}] Q: {node.question}\n"
        f"Findings: {node.findings[:1500]}"
    )


async def recursive_research(
    job: ResearchJob,
    thinker: Optional[OllamaInstance],
    writer: OllamaInstance,
    project: Optional[Project],
) -> tuple[list[ResearchNode], list[Citation], str]:
    """
    Run the full recursive research tree.
    Returns (nodes, all_citations, accumulated_context).
    """
    proj_ctx = (f"\nProject context:\n{project.context_summary}" if project else "")
    all_nodes: list[ResearchNode] = []
    all_citations: list[Citation] = []
    knowledge_base: list[str] = []
    question_count = 0

    # Root node
    root = ResearchNode(question=job.query, depth=0)
    queue: list[ResearchNode] = [root]

    while queue and question_count < MAX_TOTAL_QUESTIONS:
        node = queue.pop(0)
        if cancel_flags.get(job.id): break

        await research_node(node, job, thinker, writer, all_citations, knowledge_base)
        all_nodes.append(node)
        question_count += 1

        # Enqueue sub-questions
        for sq in node.sub_questions:
            if question_count + len(queue) >= MAX_TOTAL_QUESTIONS: break
            queue.append(ResearchNode(question=sq, depth=node.depth+1, parent=node.question))

        await step_emit(job, "Progress",
            f"{question_count} questions investigated, {len(all_citations)} sources")

    # Build full context string for synthesis
    ctx_parts = [f"## Recursive Research Results ({len(all_nodes)} nodes)\n"]
    for node in all_nodes:
        indent = "  " * node.depth
        ctx_parts.append(f"\n{indent}### {'Root: ' if node.depth==0 else ''}{node.question}")
        if node.parent:
            ctx_parts.append(f"{indent}*(sub-question of: {node.parent})*")
        ctx_parts.append(f"{indent}{node.findings[:2000]}")
        if node.citations:
            ctx_parts.append(f"{indent}*Sources: {', '.join(c.domain for c in node.citations[:5])}*")

    full_ctx = "\n".join(ctx_parts)

    # Deduplicate citations
    seen_urls: set[str] = set()
    deduped: list[Citation] = []
    for c in all_citations:
        if c.url not in seen_urls:
            seen_urls.add(c.url)
            deduped.append(c)

    return all_nodes, deduped, full_ctx


async def run_guide_output(job: ResearchJob, ctx: str,
                            thinker: Optional[OllamaInstance],
                            writer: OllamaInstance,
                            project: Optional[Project]) -> str:
    """
    Deep recursive guide:
    1. Recursive research tree builds a knowledge base
    2. Thinker plans section outline from ALL gathered knowledge
    3. Writer generates each section with full context + continuity
    """
    proj_ctx = (f"\n\nProject context:\n{project.context_summary}" if project else "")

    # Run recursive research
    await step_emit(job, "Deep research", "Recursively investigating topic…")
    nodes, all_cits, full_ctx = await recursive_research(job, thinker, writer, project)

    # Update job citations from recursive research
    job.citations = all_cits
    await broadcast(job.id, {"type":"citations","citations":[c.to_dict() for c in all_cits]})

    # Plan sections from the full knowledge base
    await step_emit(job, "Outline", "Planning sections from gathered knowledge…")
    use_inst = thinker or writer
    outline_prompt = (
        f"Topic: {job.query}{proj_ctx}\n\n"
        f"Knowledge gathered:\n{full_ctx[:6000]}\n\n"
        "Based on everything researched, plan 6-10 section headings for a comprehensive guide. "
        "Sections should reflect what was actually found, not generic placeholders. "
        "Respond ONLY with a JSON array of strings."
    )
    raw_outline = await collect_ollama(use_inst, outline_prompt,
        "You are a guide architect. Return only a JSON array of section titles.", job.id, timeout_secs=THINKER_PLAN_TIMEOUT)

    sections: list[str] = []
    try:
        sections = json.loads(raw_outline[raw_outline.index("["):raw_outline.rindex("]")+1])
        sections = [str(s) for s in sections[:10]]
    except Exception:
        # Fallback: use node questions as sections
        sections = [n.question for n in nodes[:8]]

    await step_emit(job, "Writing", f"{len(sections)} sections from {len(nodes)} research nodes")

    # Build citation reference list for LLM to cite inline
    cit_ref = "\n".join(f"[{i+1}] {c.title} — {c.url}" for i, c in enumerate(all_cits[:30]))

    all_parts: list[str] = [f"# {job.query}\n\n"]
    slot_w = slot_for(ModelTier.WRITER)
    slot_on(slot_w, writer, job.id, "writing")

    for i, section in enumerate(sections, 1):
        if cancel_flags.get(job.id): break
        await step_emit(job, f"§{i}/{len(sections)}", section[:60])

        # Find the most relevant research nodes for this section
        relevant_nodes = [n for n in nodes if
            any(w.lower() in n.question.lower() or w.lower() in n.findings.lower()
                for w in section.lower().split()[:5])][:4]
        node_ctx = "\n\n".join(
            f"From '{n.question}':\n{n.findings[:1500]}"
            for n in (relevant_nodes or nodes[:3])
        )

        sec_prompt = (
            f"Guide topic: {job.query}\n\n"
            f"Section to write: ## {section}\n\n"
            f"Directly relevant research findings:\n{node_ctx[:5000]}\n\n"
            f"Full knowledge base summary:\n{full_ctx[:3000]}\n\n"
            f"{proj_ctx}\n"
            f"Previously written (for continuity):\n{''.join(all_parts)[-1500:]}\n\n"
            f"Available citations:\n{cit_ref[:2000]}\n\n"
            f"Write a thorough, specific section titled '## {section}'. "
            "Use the actual research findings — specific facts, numbers, names, mechanisms. "
            "Do NOT be vague or generic. Cite sources as [1], [2] etc. "
            "Include code, commands, configs, or step-by-step instructions where relevant."
        )
        sec_parts: list[str] = []
        async for tok in stream_ollama(writer, sec_prompt, GUIDE_SYS, job.id, slot_w):
            sec_parts.append(tok)
            if cancel_flags.get(job.id): break
        all_parts.append("".join(sec_parts) + "\n\n")

    slot_off(slot_w)

    # Append references
    if all_cits:
        all_parts.append("\n\n## References\n\n")
        for i, c in enumerate(all_cits[:50], 1):
            all_parts.append(f"[{i}] [{c.title}]({c.url})  \n")

    return "".join(all_parts)


# ══════════════════════════════════════════════════════════════════════════════
#  Filestore output
# ══════════════════════════════════════════════════════════════════════════════

async def run_filestore_output(job: ResearchJob, ctx: str,
                                thinker: Optional[OllamaInstance],
                                writer: OllamaInstance,
                                project: Optional[Project]) -> str:
    """
    Produce a full file tree:
    1. Thinker plans the file/directory structure
    2. Writer generates each file's content
    3. Parse and materialise to disk
    """
    proj_ctx = (f"\n\nProject context:\n{project.context_summary}" if project else "")
    await step_emit(job, "Planning files", "Designing file structure…")

    plan_prompt = (
        f"Task: {job.query}\n\nSources:\n{ctx[:3000]}{proj_ctx}\n\n"
        "List ALL files that need to be created. "
        "Respond ONLY with a JSON array of file paths, e.g. "
        '["docker-compose.yml","app/main.py","app/config.py","README.md"]'
    )
    use_inst = thinker or writer
    raw_plan = await collect_ollama(use_inst, plan_prompt,
        "You are a software architect. Return only a JSON array of file paths.", job.id, timeout_secs=THINKER_PLAN_TIMEOUT)

    file_paths: list[str] = []
    try:
        file_paths = json.loads(raw_plan[raw_plan.index("["):raw_plan.rindex("]")+1])
        file_paths = [str(p) for p in file_paths if "." in p][:30]
    except Exception:
        file_paths = []

    if not file_paths:
        # Fallback: ask writer to produce everything in one shot
        await step_emit(job, "Generating", "Producing all files…")
        slot_w = slot_for(ModelTier.WRITER)
        slot_on(slot_w, writer, job.id, "writing")
        all_content: list[str] = []
        async for tok in stream_ollama(writer,
            f"Task: {job.query}\n\nSources:\n{ctx[:5000]}{proj_ctx}\n\nProduce ALL necessary files.",
            FILESTORE_SYS, job.id, slot_w):
            all_content.append(tok)
            if cancel_flags.get(job.id): break
        slot_off(slot_w)
        raw = "".join(all_content)
        job.file_tree = parse_file_tree(raw)
        await materialise_file_tree(job, project)
        return raw

    await step_emit(job, "Files planned", f"{len(file_paths)} files")
    slot_w = slot_for(ModelTier.WRITER)
    slot_on(slot_w, writer, job.id, "writing")

    all_output: list[str] = []
    completed_files: dict[str, str] = {}

    for i, fpath in enumerate(file_paths, 1):
        if cancel_flags.get(job.id): break
        await step_emit(job, f"File {i}/{len(file_paths)}", fpath)
        ext = Path(fpath).suffix
        file_prompt = (
            f"Task: {job.query}\n\nFile to create: {fpath}\n\n"
            f"Sources:\n{ctx[:3000]}{proj_ctx}\n\n"
            f"Already created files:\n{chr(10).join(completed_files.keys())}\n\n"
            f"Write the COMPLETE contents of {fpath}. "
            f"Wrap it like:\n=== FILE: {fpath} ===\n<contents>\n=== END ==="
        )
        file_parts: list[str] = []
        async for tok in stream_ollama(writer, file_prompt, FILESTORE_SYS, job.id, slot_w):
            file_parts.append(tok)
            if cancel_flags.get(job.id): break
        file_raw = "".join(file_parts)
        all_output.append(file_raw)
        # Parse this file immediately
        parsed = parse_file_tree(file_raw)
        if not parsed:
            # Wrap it ourselves if LLM forgot
            parsed = {fpath: file_raw.strip()}
        completed_files.update(parsed)
        await broadcast(job.id, {"type":"file_created","path":fpath})

    slot_off(slot_w)
    job.file_tree = completed_files
    await materialise_file_tree(job, project)

    # Generate a README summary
    summary = f"# {job.query}\n\n## Files Created\n\n"
    for p in completed_files:
        summary += f"- `{p}`\n"
    summary += f"\n## Sources\n\n"
    for i, c in enumerate(job.citations, 1):
        summary += f"[{i}] [{c.title}]({c.url})\n"
    return summary + "\n\n" + "\n\n".join(all_output)


# ══════════════════════════════════════════════════════════════════════════════
#  Main pipelines
# ══════════════════════════════════════════════════════════════════════════════

async def run_single(job: ResearchJob, project: Optional[Project] = None):
    """
    Single-agent mode.
    Report: one search round → write.
    Guide/Files: use full recursive engine.
    Code: use coding pipeline (all three agents).
    """
    writer  = await get_instance(ModelTier.WRITER) or await get_instance(ModelTier.THINKER)
    thinker = await get_instance(ModelTier.THINKER)
    if not writer:
        job.status = JobStatus.ERROR; job.error = "No Ollama instance available"; return

    slot_w = slot_for(ModelTier.WRITER)
    slot_on(slot_w, writer, job.id, "active")

    if job.output_mode == OutputMode.CODE:
        slot_off(slot_w)
        await run_code_pipeline(job, project)
        return

    if job.output_mode == OutputMode.GUIDE:
        job.status = JobStatus.SEARCHING
        job.result = await run_guide_output(job, "", thinker, writer, project)
        slot_off(slot_w)
        return

    if job.output_mode == OutputMode.FILESTORE:
        _, ctx = await _search_phase(job)
        job.status = JobStatus.WRITING
        job.result = await run_filestore_output(job, ctx, thinker, writer, project)
        slot_off(slot_w)
        return

    # Standard report: one search + write
    _, ctx = await _search_phase(job)
    proj_ctx = (f"\n\nProject context:\n{project.context_summary}" if project else "")
    # Iterative context: include prior result when user is drilling deeper
    iter_ctx = ""
    if job.prior_context and job.context_mode == "continue":
        iter_ctx = (
            f"\n\n## Prior Research (build on this, do not repeat)\n"
            f"{job.prior_context[:3000]}"
        )
    job.status = JobStatus.WRITING
    await step_emit(job, "Writing", f"{writer.name}")
    cit_ref = "\n".join(f"[{i+1}] {c.title} — {c.url}" for i, c in enumerate(job.citations[:20]))
    parts: list[str] = []
    async for tok in stream_ollama(writer,
        f"Research query: {job.query}{proj_ctx}{iter_ctx}\n\n{ctx}\n\nCitations:\n{cit_ref}\n\n"
        "Write a comprehensive research report. Cite sources as [1], [2] etc.",
        WRITE_SYS, job.id, slot_w):
        parts.append(tok)
        if cancel_flags.get(job.id): break
    job.result = "".join(parts)
    slot_off(slot_w)


async def run_deep(job: ResearchJob, project: Optional[Project] = None):
    """
    Deep mode: always uses the recursive research engine.
    Thinker does slow reasoning over the accumulated knowledge base,
    Writer produces the final output.
    """
    thinker = await get_instance(ModelTier.THINKER)
    writer  = await get_instance(ModelTier.WRITER)
    analyst = await get_instance(ModelTier.ANALYST)
    slot_t  = slot_for(ModelTier.THINKER)
    slot_a  = slot_for(ModelTier.ANALYST)

    if not (thinker or writer):
        await run_single(job, project); return

    use_writer = writer or thinker

    if job.output_mode == OutputMode.CODE:
        await run_code_pipeline(job, project)
        return

    if job.output_mode == OutputMode.GUIDE:
        job.status = JobStatus.SEARCHING
        job.result = await run_guide_output(job, "", thinker, use_writer, project)
        return

    if job.output_mode == OutputMode.FILESTORE:
        # Recursive research first, then file generation
        await step_emit(job, "Deep research", "Recursively investigating…")
        nodes, all_cits, full_ctx = await recursive_research(job, thinker, use_writer, project)
        job.citations = all_cits
        await broadcast(job.id, {"type":"citations","citations":[c.to_dict() for c in all_cits]})
        job.status = JobStatus.WRITING
        job.result = await run_filestore_output(job, full_ctx, thinker, use_writer, project)
        return

    # Deep report: recursive research → thinker synthesises → writer drafts → analyst checks
    await step_emit(job, "Deep research", "Recursively investigating…")
    job.status = JobStatus.SEARCHING

    nodes, all_cits, full_ctx = await recursive_research(job, thinker, use_writer, project)
    job.citations = all_cits
    await broadcast(job.id, {"type":"citations","citations":[c.to_dict() for c in all_cits]})

    if cancel_flags.get(job.id): return

    # Thinker synthesises the knowledge base
    thinking = full_ctx
    if thinker:
        slot_on(slot_t, thinker, job.id, "thinking")
        job.status = JobStatus.THINKING
        proj_ctx = (f"\n\nProject context:\n{project.context_summary}" if project else "")
        await step_emit(job, "Synthesising", f"{thinker.name} integrating {len(nodes)} research nodes…")
        think_sys = (
            "You are a senior researcher synthesising a deep investigation. "
            "Integrate all findings, resolve contradictions, identify the key insights, "
            "and create a clear writing plan for a comprehensive report."
        )
        thinking = await collect_ollama(thinker,
            f"Topic: {job.query}{proj_ctx}\n\n{full_ctx[:12000]}\n\n"
            "Synthesise all findings and produce a structured writing plan.",
            think_sys, job.id, slot_t, timeout_secs=THINKER_THINK_TIMEOUT)
        slot_off(slot_t)

    if cancel_flags.get(job.id): return

    # Writer produces final report
    slot_w = slot_for(ModelTier.WRITER)
    slot_on(slot_w, use_writer, job.id, "writing")
    job.status = JobStatus.WRITING
    await step_emit(job, "Writing", f"{use_writer.name} producing final report…")
    cit_ref = "\n".join(f"[{i+1}] {c.title} — {c.url}" for i, c in enumerate(all_cits[:40]))
    proj_ctx = (f"\n\nProject context:\n{project.context_summary}" if project else "")
    draft_parts: list[str] = []
    async for tok in stream_ollama(use_writer,
        f"Topic: {job.query}{proj_ctx}\n\n"
        f"Research synthesis:\n{thinking[:8000]}\n\n"
        f"Full knowledge base:\n{full_ctx[:6000]}\n\n"
        f"Available citations:\n{cit_ref}\n\n"
        "Write a comprehensive, deeply detailed research report. "
        "Use ## headers, cite every claim as [N], include specific facts not vague generalities.",
        WRITE_SYS, job.id, slot_w):
        draft_parts.append(tok)
        if cancel_flags.get(job.id): break
    slot_off(slot_w)
    draft = "".join(draft_parts)

    if cancel_flags.get(job.id): job.result = draft; return

    # Analyst verification with timeout
    if analyst:
        job.result = await run_analyst_phase(job, draft, analyst, slot_a)
    else:
        job.result = draft

    # Append references
    if all_cits and "## References" not in job.result:
        refs = "\n\n## References\n\n" + "\n".join(
            f"[{i+1}] [{c.title}]({c.url})  " for i, c in enumerate(all_cits[:50], 1)
        )
        job.result += refs


async def run_parallel(job: ResearchJob, project: Optional[Project] = None):
    thinker = await get_instance(ModelTier.THINKER)
    writer  = await get_instance(ModelTier.WRITER)
    slot_t  = slot_for(ModelTier.THINKER)

    if not thinker: await run_single(job, project); return

    _, ctx = await _search_phase(job)
    proj_ctx = (f"\n\nProject context:\n{project.context_summary}" if project else "")

    # Decompose
    job.status = JobStatus.THINKING
    await step_emit(job, "Decompose", "Breaking into sub-tasks…")
    slot_on(slot_t, thinker, job.id, "thinking")

    raw = await collect_ollama(thinker, job.query,
        "Break this query into 2-4 focused sub-questions. "
        "Respond ONLY with a JSON array of strings.",
        job.id, slot_t, timeout_secs=THINKER_PLAN_TIMEOUT)
    slot_off(slot_t)

    sub_qs: list[str] = []
    try:
        sub_qs = json.loads(raw[raw.index("["):raw.rindex("]")+1])
        sub_qs = [str(q) for q in sub_qs[:4]]
    except Exception:
        sub_qs = [job.query]

    await step_emit(job, "Tasks", f"{len(sub_qs)} parallel sub-tasks")
    job.status = JobStatus.WRITING
    use_w = writer or thinker

    async def research_sub(q: str, idx: int) -> str:
        await broadcast(job.id, {"type":"step","t":time.time(),"label":f"Task {idx+1}","detail":q[:80]})
        # Each sub-question searches independently for its own sources
        try:
            class _SubJob:
                id = job.id
                sources = job.sources
                citations: list = []
            sub_cits, sub_ctx = await gather_all_sources(q, _SubJob())
            # Merge new citations into parent job (deduplicate by URL)
            existing_urls = {c.url for c in job.citations}
            for c in sub_cits:
                if c.url not in existing_urls:
                    job.citations.append(c)
                    existing_urls.add(c.url)
            if sub_cits:
                await broadcast(job.id, {"type":"citations","citations":[c.to_dict() for c in sub_cits]})
        except Exception as e:
            log.warning("Sub-search failed for %r: %s", q, e)
            sub_ctx = ctx  # fall back to parent search context
        parts: list[str] = []
        async for tok in stream_ollama(use_w,
            f"Sub-question: {q}\n\nSources:\n{sub_ctx[:3000]}{proj_ctx}",
            "Answer this sub-question thoroughly using the provided sources. "
            "Cite as [1],[2] etc. Use facts from the sources — do not speculate.", job.id):
            parts.append(tok)
            if cancel_flags.get(job.id): break
        return "".join(parts)

    # Run all sub-questions truly concurrently
    sub_results = list(await asyncio.gather(*[research_sub(q,i) for i,q in enumerate(sub_qs)]))
    if cancel_flags.get(job.id): job.result="\n\n".join(sub_results); return

    # Synthesise
    await step_emit(job, "Synthesise", "Merging results…")
    slot_on(slot_t, thinker, job.id, "synthesising")
    combined = "\n\n".join(f"### Sub-question {i+1}: {sub_qs[i]}\n{r}" for i,r in enumerate(sub_results))
    iter_ctx_par = ""
    if job.prior_context and job.context_mode == "continue":
        iter_ctx_par = f"\n\nPrior research context (build on, don't repeat):\n{job.prior_context[:2000]}"
    synth_parts: list[str] = []
    async for tok in stream_ollama(thinker,
        f"Query: {job.query}\n\nSub-results:\n{combined}\n\nSources:\n{ctx}{proj_ctx}{iter_ctx_par}\n\nSynthesise.",
        WRITE_SYS, job.id, slot_t):
        synth_parts.append(tok)
        if cancel_flags.get(job.id): break
    slot_off(slot_t)
    job.result = "".join(synth_parts)


async def run_job(job: ResearchJob):
    project: Optional[Project] = None
    if job.project_id and job.project_id in projects:
        project = projects[job.project_id]

    try:
        cancel_flags[job.id] = False
        await broadcast(job.id, {"type":"status","status":job.status,"job_id":job.id})

        if   job.mode == AgentMode.DEEP:     await run_deep(job, project)
        elif job.mode == AgentMode.PARALLEL: await run_parallel(job, project)
        else:                                await run_single(job, project)

        job.status = JobStatus.CANCELLED if cancel_flags.get(job.id) else JobStatus.DONE

        # Update project context
        if project:
            thinker = await get_instance(ModelTier.THINKER)
            await update_project_context(project, job, thinker)

    except Exception as e:
        log.exception("Job %s failed", job.id)
        job.status = JobStatus.ERROR; job.error = str(e)
    finally:
        job.finished_at = time.time()
        job.token_count = sum(s.tokens for s in agent_slots)
        cancel_flags.pop(job.id, None)
        history.insert(0, job)
        if len(history) > 200: history.pop()
        chain_info: dict = {}
        if job.chain_ctx:
            chain_info = {
                "chain_id":       job.chain_ctx.chain_id,
                "run_number":     job.chain_ctx.run_number,
                "files_done":     job.chain_ctx.files_done,
                "files_pending":  job.chain_ctx.files_pending,
                "is_complete":    job.chain_ctx.is_complete,
                "chain_continues": job.chain_continues,
            }
        await broadcast(job.id, {
            "type":"done","status":job.status,"job_id":job.id,
            "result":job.result or "","error":job.error or "",
            "elapsed":round(job.finished_at-job.created_at,1),
            "tokens":job.token_count,
            "citations":[c.to_dict() for c in job.citations],
            "file_tree":list(job.file_tree.keys()),
            **chain_info,
        })
        jobs.pop(job.id, None)

    # ── Persist to database ───────────────────────────────────────────────────
    try:
        await DB.save_job(job)
        if project:
            await DB.save_project(project)
    except Exception as e:
        log.error("DB save failed for job %s: %s", job.id, e)

    # ── Save chain context for continuation ───────────────────────────────────
    if job.chain_ctx and not job.chain_ctx.is_complete:
        chain_store[job.chain_ctx.chain_id] = job.chain_ctx
        log.info("Chain %s saved: %d done, %d pending",
                 job.chain_ctx.chain_id,
                 len(job.chain_ctx.files_done),
                 len(job.chain_ctx.files_pending))


# ══════════════════════════════════════════════════════════════════════════════
#  Pydantic models
# ══════════════════════════════════════════════════════════════════════════════



class ResearchRequest(BaseModel):
    query:          str        = Field(..., min_length=1, max_length=8000)
    mode:           AgentMode  = AgentMode.SINGLE
    output_mode:    OutputMode = OutputMode.REPORT
    sources:        list[str]  = Field(default_factory=list)
    project_id:     Optional[str] = None
    context:        Optional[str] = None   # prior research text to include as context
    context_mode:   str = "fresh"          # "fresh" | "continue" — whether to include prior context

class ChainContinueRequest(BaseModel):
    """Trigger the next run of a chained coding job."""
    chain_id:   str                       # from chain_continue WS message
    job_id:     str                       # original job that produced the chain
    project_id: Optional[str] = None

class SourceTestRequest(BaseModel):
    source_id: str

class SourceUpdateRequest(BaseModel):
    sources: list[dict]

class InstanceUpdateRequest(BaseModel):
    instances: list[dict]

class WebSearchConfigRequest(BaseModel):
    engine:        Optional[str]   = None
    result_count:  Optional[int]   = None
    crawl_depth:   Optional[int]   = None
    crawl_breadth: Optional[int]   = None
    crawl_timeout: Optional[float] = None
    include_archive: Optional[bool]= None
    safe_search:   Optional[int]   = None

class ProjectCreateRequest(BaseModel):
    name:        str
    description: str = ""
    output_mode: OutputMode = OutputMode.REPORT


# ══════════════════════════════════════════════════════════════════════════════
#  Config file helpers  (vera_config.json — fallback when DB empty on restart)
# ══════════════════════════════════════════════════════════════════════════════

_CFG_FILE = Path("vera_config.json")


def _load_config_file() -> dict:
    if _CFG_FILE.exists():
        try:
            with open(_CFG_FILE) as f:
                data = json.load(f)
            log.info("Config fallback loaded from %s", _CFG_FILE)
            return data
        except Exception as e:
            log.warning("Cannot read %s: %s", _CFG_FILE, e)
    return {}


def _write_config_file() -> None:
    """Snapshot current instances/sources/web_cfg → vera_config.json."""
    try:
        data = {
            "instances": [
                {"name": i.name, "host": i.host, "port": i.port,
                 "tier": i.tier.value, "model": i.model,
                 "ctx_size": i.ctx_size, "enabled": i.enabled}
                for i in instances
            ],
            "sources": [
                {"id": s.id, "label": s.label, "type": s.type.value,
                 "enabled": s.enabled, "config": s.config, "status": s.status}
                for s in sources
            ],
            "web_cfg": {
                "engine": web_cfg.engine, "result_count": web_cfg.result_count,
                "crawl_depth": web_cfg.crawl_depth, "crawl_breadth": web_cfg.crawl_breadth,
                "crawl_timeout": web_cfg.crawl_timeout,
                "include_archive": web_cfg.include_archive, "safe_search": web_cfg.safe_search,
            },
        }
        with open(_CFG_FILE, "w") as f:
            json.dump(data, f, indent=2)
        log.debug("Config snapshot → %s", _CFG_FILE)
    except Exception as e:
        log.warning("Cannot write %s: %s", _CFG_FILE, e)


# ══════════════════════════════════════════════════════════════════════════════
#  App
# ══════════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Database ──────────────────────────────────────────────────────────────
    await DB.init()
    log.info("Database ready")

    global sources, instances, web_cfg

    def _apply_file_cfg(fc: dict) -> None:
        global sources, instances, web_cfg
        if fc.get("sources"):
            loaded = []
            for row in fc["sources"]:
                try:
                    loaded.append(DataSource(
                        id=row["id"], label=row["label"], type=SourceType(row["type"]),
                        enabled=bool(row.get("enabled", True)),
                        config=row.get("config", {}), status=row.get("status", "unknown"),
                    ))
                except Exception as e:
                    log.warning("Config-file source skip %s: %s", row.get("id"), e)
            if loaded:
                sources = loaded
                log.info("Loaded %d sources from config file", len(sources))
        if fc.get("instances"):
            loaded = []
            for row in fc["instances"]:
                try:
                    loaded.append(OllamaInstance(
                        name=row["name"], host=row["host"], port=int(row["port"]),
                        tier=ModelTier(row["tier"]), model=row["model"],
                        ctx_size=int(row.get("ctx_size", 8192)),
                        enabled=bool(row.get("enabled", True)),
                    ))
                except Exception as e:
                    log.warning("Config-file instance skip %s: %s", row.get("name"), e)
            if loaded:
                instances = loaded
                log.info("Loaded %d instances from config file", len(instances))
        if fc.get("web_cfg"):
            wc = fc["web_cfg"]
            web_cfg.engine        = wc.get("engine", web_cfg.engine)
            web_cfg.result_count  = int(wc.get("result_count", web_cfg.result_count))
            web_cfg.crawl_depth   = int(wc.get("crawl_depth", web_cfg.crawl_depth))
            web_cfg.crawl_breadth = int(wc.get("crawl_breadth", web_cfg.crawl_breadth))
            web_cfg.crawl_timeout = float(wc.get("crawl_timeout", web_cfg.crawl_timeout))
            web_cfg.include_archive = bool(wc.get("include_archive", False))
            web_cfg.safe_search   = int(wc.get("safe_search", 0))
            log.info("Loaded web search config from config file")

    # ── Load persisted sources ────────────────────────────────────────────────
    saved_sources = await DB.load_sources()
    loaded_sources = []
    for row in saved_sources:
        try:
            loaded_sources.append(DataSource(
                id=row["id"], label=row["label"],
                type=SourceType(row["type"]),
                enabled=bool(row["enabled"]),
                config=row.get("config", {}),
                status=row.get("status", "unknown"),
            ))
        except Exception as e:
            log.warning("Skipping DB source %s (type=%r): %s", row.get("id"), row.get("type"), e)
    if loaded_sources:
        sources = loaded_sources
        log.info("Loaded %d sources from DB", len(sources))
    else:
        log.info("No valid sources in DB — trying %s", _CFG_FILE)
        _apply_file_cfg(_load_config_file())

    # ── Load persisted instances ──────────────────────────────────────────────
    saved_insts = await DB.load_instances()
    loaded_insts = []
    for row in saved_insts:
        try:
            loaded_insts.append(OllamaInstance(
                name=row["name"], host=row["host"], port=int(row["port"]),
                tier=ModelTier(row["tier"]), model=row["model"],
                ctx_size=int(row.get("ctx_size", 8192)),
                enabled=bool(row.get("enabled", True)),
            ))
        except Exception as e:
            log.warning("Skipping DB instance %s (tier=%r): %s", row.get("name"), row.get("tier"), e)
    if loaded_insts:
        instances = loaded_insts
        log.info("Loaded %d instances from DB", len(instances))
    else:
        log.info("No valid instances in DB — trying %s", _CFG_FILE)
        _apply_file_cfg(_load_config_file())

    # ── Load persisted web search config ──────────────────────────────────────
    saved_ws = await DB.load_web_search_config()
    if saved_ws:
        web_cfg.engine        = saved_ws.get("engine", web_cfg.engine)
        web_cfg.result_count  = int(saved_ws.get("result_count", web_cfg.result_count))
        web_cfg.crawl_depth   = int(saved_ws.get("crawl_depth", web_cfg.crawl_depth))
        web_cfg.crawl_breadth = int(saved_ws.get("crawl_breadth", web_cfg.crawl_breadth))
        web_cfg.crawl_timeout = float(saved_ws.get("crawl_timeout", web_cfg.crawl_timeout))
        web_cfg.include_archive = bool(saved_ws.get("include_archive", False))
        web_cfg.safe_search   = int(saved_ws.get("safe_search", 0))
        log.info("Loaded web search config from DB")
    else:
        _apply_file_cfg(_load_config_file())

    # Write a fresh snapshot so the file is always current
    _write_config_file()

    # ── Load persisted projects into memory ───────────────────────────────────
    saved_projects = await DB.load_projects()
    for row in saved_projects:
        if row["id"] not in projects:
            proj = Project(
                id=row["id"], name=row["name"],
                description=row.get("description", ""),
                output_mode=OutputMode.REPORT,
                context_summary=row.get("context_summary", ""),
                created_at=float(row.get("created_at", time.time())),
                updated_at=float(row.get("updated_at", time.time())),
            )
            projects[proj.id] = proj
    log.info("Loaded %d projects from DB", len(projects))

    # ── Load persisted bookmarks into memory ──────────────────────────────────
    saved_bmarks = await DB.load_bookmarks()
    for bm in saved_bmarks:
        bookmarks[bm["id"]] = bm
    log.info("Loaded %d bookmarks from DB", len(bookmarks))

    # ── Probe Ollama instances ────────────────────────────────────────────────
    log.info("Vera Researcher v4 starting on port 8765…")
    for inst in instances:
        mods = await list_models(inst)
        log.info("  %-10s %-28s %s", inst.name, inst.base_url,
                 f"{len(mods)} models" if mods else "UNREACHABLE")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    # Close playwright browser if it was launched
    global _pw_browser
    if _pw_browser is not None:
        try:
            await _pw_browser.close()
            log.info("Playwright browser closed")
        except Exception:
            pass
        _pw_browser = None
    await DB.close()
    log.info("Vera Researcher shut down")


app = FastAPI(title="Vera Research Agent", version="3.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOT_DIR)), name="screenshots")


# ══════════════════════════════════════════════════════════════════════════════
#  Routes — Research
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/research")
async def start_research(req: ResearchRequest, bg: BackgroundTasks):
    job = ResearchJob(
        id=str(uuid.uuid4()), query=req.query, mode=req.mode,
        output_mode=req.output_mode,
        sources=req.sources or [s.id for s in sources if s.enabled],
        status=JobStatus.QUEUED, created_at=time.time(),
        project_id=req.project_id,
        prior_context=req.context or "",
        context_mode=req.context_mode or "fresh",
    )
    jobs[job.id] = job
    # Save stub immediately so the job appears in Library even while running
    try:
        await DB.save_job(job)
    except Exception as e:
        log.warning("Early job save failed: %s", e)
    bg.add_task(run_job, job)
    return {"job_id":job.id,"status":job.status}


# In-memory chain store: chain_id → ChainContext
# (populated at end of each CODE run that needs continuation)
chain_store: dict[str, ChainContext] = {}


@app.post("/api/research/continue")
async def continue_chain(req: ChainContinueRequest, bg: BackgroundTasks):
    """
    Trigger the next run of a chained coding job.
    The frontend sends the chain_id received in the chain_continue WS message.
    """
    chain = chain_store.get(req.chain_id)
    if not chain:
        # Try to reconstruct from the original job's history
        orig = await DB.load_job_result(req.job_id)
        if not orig:
            raise HTTPException(404, f"Chain '{req.chain_id}' not found — original job may have been deleted")
        raise HTTPException(410, "Chain context expired from memory — restart the coding job")

    if chain.is_complete:
        return {"ok": False, "reason": "Chain is already complete"}

    if not chain.files_pending:
        chain.is_complete = True
        chain_store.pop(req.chain_id, None)
        return {"ok": False, "reason": "No files pending"}

    # Create a continuation job with the existing chain context
    cont_job = ResearchJob(
        id          = str(uuid.uuid4()),
        query       = chain.original_task,
        mode        = AgentMode.DEEP,      # always use all agents for coding
        output_mode = OutputMode.CODE,
        sources     = [],                  # no re-search needed
        status      = JobStatus.QUEUED,
        created_at  = time.time(),
        project_id  = req.project_id,
        chain_ctx   = chain,
    )
    jobs[cont_job.id] = cont_job
    bg.add_task(run_job, cont_job)
    return {
        "job_id":        cont_job.id,
        "chain_id":      chain.chain_id,
        "run_number":    chain.run_number,
        "files_pending": chain.files_pending,
        "files_done":    chain.files_done,
    }


@app.get("/api/research/chain/{chain_id}")
async def get_chain_status(chain_id: str):
    """Return current state of a chain."""
    chain = chain_store.get(chain_id)
    if not chain:
        raise HTTPException(404, "Chain not found")
    return {
        "chain_id":      chain.chain_id,
        "run_number":    chain.run_number,
        "original_task": chain.original_task,
        "files_planned": chain.files_planned,
        "files_done":    chain.files_done,
        "files_pending": chain.files_pending,
        "is_complete":   chain.is_complete,
        "summary":       chain.continuity_summary,
    }


class CrawlRequest(BaseModel):
    url:   str
    depth: int = 2


@app.post("/api/research/{job_id}/crawl")
async def trigger_crawl(job_id: str, req: CrawlRequest, bg: BackgroundTasks):
    """Tag a URL for deep crawl and stream results back into the job's WS channel."""
    async def _do(url: str, depth: int, jid: str):
        await broadcast(jid, {"type":"step","t":time.time(),
                               "label":"Deep crawl","detail":url[:80]})
        text = await deep_crawl_url(url, depth, web_cfg.crawl_breadth,
                                     web_cfg.crawl_timeout, job_id=jid)
        if text:
            # Create a citation for this crawl result and broadcast it
            from urllib.parse import urlparse
            dom = urlparse(url).netloc
            cit = Citation(id=str(uuid.uuid4())[:8], url=url,
                           title=f"Crawled: {dom}", snippet=text[:300],
                           source_type="crawl", full_text=text)
            await broadcast(jid, {"type":"citations","citations":[cit.to_dict_full()]})
            await broadcast(jid, {"type":"crawl_done","url":url,
                                   "chars":len(text),"title":cit.title})
            # Persist to DB if job exists
            job = jobs.get(jid)
            if job:
                job.citations.append(cit)
                try: await DB.save_job(job)
                except Exception: pass
        else:
            await broadcast(jid, {"type":"crawl_done","url":url,"chars":0,"title":url})
    bg.add_task(_do, req.url, req.depth, job_id)
    return {"ok": True, "message": f"Crawling {req.url} at depth {req.depth}"}



class ResearchChatRequest(BaseModel):
    message:       str
    context:       str = ""
    citations_ctx: str = ""
    mode:          AgentMode = AgentMode.SINGLE


@app.post("/api/research/chat")
async def research_chat(req: ResearchChatRequest):
    """Chat against the current research result — streams SSE tokens."""
    writer = await get_instance(ModelTier.WRITER) or await get_instance(ModelTier.THINKER)
    if not writer:
        raise HTTPException(503, "No model available")
    sys_p = (
        "You are a research assistant. The user has completed a research session "
        "and wants to ask follow-up questions or dive deeper. "
        "Use ONLY the provided research context to answer. "
        "If the answer is not in the context, say so and suggest a new search query. "
        "Be concise and cite sections of the research where relevant."
    )
    cit_block = ("Citations:\n" + req.citations_ctx[:2000]) if req.citations_ctx else ""
    prompt = (
        f"Research context:\n{req.context[:6000]}\n\n"
        f"{cit_block}\n\n"
        f"User question: {req.message}\n\n"
        "Answer using the research context above."
    )

    async def _stream():
        async for tok in stream_ollama(writer, prompt, sys_p, "chat", timeout_secs=WRITER_TIMEOUT):
            yield f"data: {json.dumps({'token': tok})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")




@app.post("/api/agent/stop")
async def stop_agent(payload: dict):
    jid = payload.get("job_id","")
    if jid in cancel_flags: cancel_flags[jid]=True; return {"ok":True}
    return {"ok":False,"reason":"job not found"}


@app.get("/api/agents/status")
async def agent_status():
    return {"slots":[{"id":s.id,"tier":s.tier,"status":s.status,"model":s.model,
        "tokens":s.tokens,"job_id":s.job_id,
        "elapsed":round(time.time()-s.started_at,1) if s.started_at and s.status!="idle" else None}
        for s in agent_slots]}


# ── History ──────────────────────────────────────────────────────────────────

@app.get("/api/history")
async def get_history(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    project_id: Optional[str] = None,
    search: Optional[str] = None,
):
    """
    Load research history from the database.
    Supports pagination, project filtering, and full-text search.
    In-flight jobs (not yet in DB) are prepended from in-memory state.
    """
    db_rows, _total = await DB.load_history(
        limit=limit, offset=offset,
        project_id=project_id, search=search,
    )

    # Prepend any currently running jobs not yet flushed to DB
    live = [
        {
            "id": j.id, "query": j.query, "mode": j.mode,
            "output_mode": j.output_mode, "status": j.status,
            "created_at": j.created_at, "finished_at": None,
            "token_count": 0, "citation_count": 0, "has_files": False,
            "error": None, "result_snippet": "Running…",
        }
        for j in jobs.values()
        if not any(r.get("id") == j.id for r in db_rows)
    ]

    return live + db_rows


@app.delete("/api/history/{job_id}")
async def delete_history(job_id: str):
    deleted = await DB.delete_job(job_id)
    # Also remove from in-memory list if present
    global history
    history = [j for j in history if j.id != job_id]
    return {"deleted": deleted}


@app.get("/api/history/{job_id}/result")
async def get_result(job_id: str):
    # Check in-memory first (job might still be running / just finished)
    mem_job = next((j for j in history if j.id == job_id), None)
    if mem_job:
        manifest = await DB.list_generated_files(job_id)
        return {
            "result":        mem_job.result,
            "steps":         mem_job.steps,
            "citations":     [c.to_dict() for c in mem_job.citations],
            "mode":          mem_job.mode,
            "output_mode":   mem_job.output_mode,
            "elapsed":       round((mem_job.finished_at or mem_job.created_at) - mem_job.created_at, 1),
            "tokens":        mem_job.token_count,
            "file_tree":     list(mem_job.file_tree.keys()),
            "file_manifest": manifest,
        }
    # Fall back to DB
    row = await DB.load_job_result(job_id)
    if not row:
        raise HTTPException(404, "Job not found")
    return row


@app.get("/api/history/{job_id}/files")
async def list_job_files(job_id: str):
    """List generated file manifest (path + size, no content)."""
    manifest = await DB.list_generated_files(job_id)
    return {"job_id": job_id, "files": manifest}


@app.get("/api/history/{job_id}/files/{file_path:path}")
async def get_job_file(job_id: str, file_path: str):
    """Download a single generated file by path."""
    from fastapi.responses import Response as FR
    content = await DB.get_generated_file(job_id, file_path)
    if content is None:
        # Fall back to on-disk copy
        disk_path = PROJECTS_DIR / "standalone" / job_id / "files" / file_path
        if disk_path.exists():
            content = disk_path.read_text(encoding="utf-8", errors="replace")
        else:
            raise HTTPException(404, f"File '{file_path}' not found")
    ext = Path(file_path).suffix.lower()
    ct = {
        ".py":"text/x-python",".js":"text/javascript",".ts":"text/typescript",
        ".html":"text/html",".css":"text/css",".json":"application/json",
        ".yaml":"text/yaml",".yml":"text/yaml",".md":"text/markdown",
        ".sh":"text/x-sh",".toml":"text/plain",".env":"text/plain",
        ".txt":"text/plain",".xml":"text/xml",".sql":"text/x-sql",
        ".rs":"text/x-rust",".go":"text/x-go",".dockerfile":"text/plain",
    }.get(ext, "text/plain")
    return FR(content=content, media_type=ct,
              headers={"Content-Disposition": f'attachment; filename="{Path(file_path).name}"'})


@app.get("/api/history/{job_id}/files.zip")
async def download_job_files_zip(job_id: str):
    """Download all generated files for a job as a ZIP."""
    import io, zipfile
    from fastapi.responses import Response as FR
    files = await DB.load_generated_files(job_id)
    if not files:
        # Fall back to on-disk
        disk = PROJECTS_DIR / "standalone" / job_id / "files"
        if disk.exists():
            zip_path = PROJECTS_DIR / "standalone" / job_id / "files.zip"
            shutil.make_archive(str(zip_path.with_suffix("")), "zip", str(disk))
            return FileResponse(str(zip_path), media_type="application/zip",
                                filename=f"job_{job_id[:8]}_files.zip")
        raise HTTPException(404, "No generated files for this job")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    buf.seek(0)
    return FR(content=buf.read(), media_type="application/zip",
              headers={"Content-Disposition": f'attachment; filename="job_{job_id[:8]}_files.zip"'})




# ── Sources ───────────────────────────────────────────────────────────────────

@app.get("/api/sources")
async def get_sources():
    return [asdict(s) for s in sources]


@app.post("/api/sources/update")
async def update_sources(req: SourceUpdateRequest):
    """Full replace of sources list from UI."""
    global sources
    new: list[DataSource] = []
    for d in req.sources:
        try:
            new.append(DataSource(
                id=d["id"], label=d["label"],
                type=SourceType(d["type"]), enabled=bool(d.get("enabled",True)),
                config=d.get("config",{}), status=d.get("status","unknown"),
            ))
        except Exception as e:
            raise HTTPException(400, f"Invalid source: {e}")
    sources = new
    await DB.save_sources(sources)
    _write_config_file()
    return {"ok":True,"count":len(sources)}


@app.post("/api/sources/add")
async def add_source(d: dict):
    """Add a single source and persist immediately."""
    try:
        src = DataSource(id=d["id"],label=d["label"],type=SourceType(d["type"]),
                         enabled=bool(d.get("enabled",True)),config=d.get("config",{}))
        # Remove any existing source with the same id first
        global sources
        sources = [s for s in sources if s.id != src.id]
        sources.append(src)
        await DB.save_sources(sources)
        _write_config_file()
        return {"ok":True}
    except Exception as e:
        raise HTTPException(400,str(e))


@app.delete("/api/sources/{source_id}")
async def delete_source(source_id:str):
    global sources
    before=len(sources); sources=[s for s in sources if s.id!=source_id]
    return {"deleted":before-len(sources)}


@app.post("/api/sources/test")
async def test_source(req: SourceTestRequest):
    src=next((s for s in sources if s.id==req.source_id),None)
    if not src: raise HTTPException(404,"Source not found")
    ok,detail=False,"Not implemented"

    if src.id=="searxng":
        host=src.config.get("host","http://llm.int:8888")
        try:
            async with httpx.AsyncClient(timeout=8.0) as c:
                # Test with a simple search to verify results are returned, not just connectivity
                r=await c.get(f"{host.rstrip('/')}/search",
                    params={"q":"test","format":"json","language":"en"})
                data=r.json()
                count=len(data.get("results",[]))
                ok=r.status_code<400; detail=f"HTTP {r.status_code} · {count} results"
        except Exception as e: detail=str(e)

    elif src.id=="brave":
        try:
            key=src.config.get("api_key","")
            if not key: detail="No API key configured"; ok=False
            else:
                async with httpx.AsyncClient(timeout=8.0) as c:
                    r=await c.get("https://api.search.brave.com/res/v1/web/search",
                        params={"q":"test","count":1},
                        headers={"Accept":"application/json","X-Subscription-Token":key})
                    ok=r.status_code==200; detail=f"HTTP {r.status_code}"
        except Exception as e: detail=str(e)

    elif src.type==SourceType.NEO4J:
        uri=src.config.get("uri","bolt://localhost:7687")
        user=src.config.get("user","neo4j")
        password=src.config.get("password","")

        # ── Strategy A: try Vera session driver first (no new connection needed) ──
        vera_tried=False
        try:
            from Vera.ChatUI.api.session import sessions as _vsess, get_or_create_vera as _gv  # type:ignore
            if _vsess:
                sid=sorted(_vsess.keys(),reverse=True)[0]
                vera=_gv(sid)
                drv=vera.mem.graph._driver  # sync driver
                with drv.session() as db:
                    n=db.run("MATCH (n) RETURN count(n) AS n").single()["n"]
                    # Run a sample text search to prove it actually returns data
                    sample=list(db.run(
                        "MATCH (n) WHERE n.text IS NOT NULL OR n.name IS NOT NULL "
                        "RETURN coalesce(n.text,n.name,'') AS t LIMIT 3"
                    ))
                    sample_texts=[r["t"][:40] for r in sample if r["t"]]
                ok=True
                detail=(f"Connected via Vera session · {n} nodes"
                        +(f" · samples: {sample_texts}" if sample_texts else " · no text nodes found"))
                vera_tried=True
        except Exception as ve:
            log.debug("neo4j via Vera session: %s", ve)

        # ── Strategy B: direct async connection ──────────────────────────────────
        if not vera_tried:
            try:
                from neo4j import AsyncGraphDatabase  # type:ignore
                drv=AsyncGraphDatabase.driver(uri,auth=(user,password))
                await drv.verify_connectivity()
                async with drv.session() as s:
                    rec=await (await s.run("MATCH (n) RETURN count(n) AS n LIMIT 1")).single()
                    n=rec["n"] if rec else 0
                    sample_res=await s.run(
                        "MATCH (n) WHERE n.text IS NOT NULL OR n.name IS NOT NULL "
                        "RETURN coalesce(n.text,n.name,'') AS t LIMIT 3"
                    )
                    sample_texts=[r["t"][:40] async for r in sample_res if r["t"]]
                await drv.close()
                ok=True
                detail=(f"Direct connection · {n} nodes"
                        +(f" · samples: {sample_texts}" if sample_texts else " · no text nodes found"))
            except ImportError: detail="neo4j not installed (pip install neo4j)"
            except Exception as e: detail=str(e)

    elif src.type==SourceType.CHROMA:
        try:
            import chromadb, glob as _glob, os as _os  # type:ignore
            dir_val=src.config.get("directory","").strip()
            host=src.config.get("host","localhost")
            port=int(src.config.get("port",8000))

            clients_info = []  # list of (client, label)

            if dir_val:
                # Expand globs + comma-separated paths, then auto-detect sub-stores
                raw_paths=[p.strip() for p in dir_val.split(",") if p.strip()]
                candidate_roots=[]
                for p in raw_paths:
                    g=_glob.glob(p)
                    candidate_roots.extend(g if g else [p])
                store_paths=[]
                for root in candidate_roots:
                    store_paths.extend(_find_chroma_stores(root))
                seen_test=set()
                for path in store_paths:
                    real=_os.path.realpath(path)
                    if real in seen_test: continue
                    seen_test.add(real)
                    try:
                        c=chromadb.PersistentClient(path=path)
                        clients_info.append((c, _os.path.basename(path.rstrip("/"))))
                    except Exception as exc:
                        clients_info.append((None, f"{_os.path.basename(path)}: {exc}"))
            else:
                try:
                    c=chromadb.HttpClient(host=host,port=port)
                    c.heartbeat()
                    clients_info.append((c, f"http:{host}:{port}"))
                except Exception as exc:
                    clients_info.append((None, f"http:{host}:{port}: {exc}"))

            parts=[]
            all_ok=True
            for client, label in clients_info:
                if client is None:
                    parts.append(f"✗ {label}")
                    all_ok=False
                    continue
                try:
                    cols=client.list_collections()
                    total_docs=sum(col.count() for col in cols)
                    # Try a sample query on the first non-empty collection
                    sample_ok=""
                    for col in cols:
                        if col.count()>0:
                            try:
                                col.query(query_texts=["test"],n_results=1)
                                sample_ok=" ✓ query OK"
                            except Exception as qe:
                                sample_ok=f" ⚠ query failed: {qe}"
                            break
                    parts.append(f"✓ {label}: {len(cols)} col(s), {total_docs} docs{sample_ok}")
                except Exception as exc:
                    parts.append(f"✗ {label}: {exc}")
                    all_ok=False

            ok=all_ok and bool(clients_info)
            detail=" | ".join(parts) if parts else "No directories configured"
        except ImportError: detail="chromadb not installed (pip install chromadb)"
        except Exception as e: detail=str(e)

    elif src.type==SourceType.REDIS:
        try:
            import redis.asyncio as aioredis  # type:ignore
            r=aioredis.Redis(host=src.config.get("host","localhost"),port=int(src.config.get("port",6379)),
                password=src.config.get("password") or None,db=int(src.config.get("db",0)),decode_responses=True)
            await r.ping()
            prefix=src.config.get("prefix","vera:")
            count=await r.dbsize()
            await r.aclose(); ok=True; detail=f"PONG · {count} keys"
        except ImportError: detail="redis package not installed (pip install redis)"
        except Exception as e: detail=str(e)

    elif src.type==SourceType.GITHUB:
        token=src.config.get("token","")
        if not token: detail="No token configured — add a GitHub personal access token"; ok=False
        else:
            try:
                async with httpx.AsyncClient(timeout=8.0) as c:
                    r=await c.get("https://api.github.com/rate_limit",
                        headers={"Authorization":f"Bearer {token}",
                                 "Accept":"application/vnd.github+json",
                                 "X-GitHub-Api-Version":"2022-11-28"})
                    if r.status_code==200:
                        rl=r.json().get("resources",{}).get("search",{})
                        ok=True; detail=f"Token valid · search quota: {rl.get('remaining','?')}/{rl.get('limit','?')}"
                    elif r.status_code==401: detail="401 Unauthorized — token is invalid or expired"
                    else: detail=f"HTTP {r.status_code}"
            except Exception as e: detail=str(e)

    elif src.type==SourceType.WEB_ARCHIVE:
        try:
            async with httpx.AsyncClient(timeout=8.0) as c:
                r=await c.get("http://web.archive.org/cdx/search/cdx",
                    params={"url":"example.com","output":"json","limit":"1"})
                ok=r.status_code<400; detail=f"Wayback Machine reachable · HTTP {r.status_code}"
        except Exception as e: detail=str(e)

    elif src.type==SourceType.WEB_CRAWL:
        ok=True; detail="Web crawl is built-in — no external service required"

    elif src.type==SourceType.NEWS:
        ok=True; detail="News source uses public API — no auth required"

    src.status="ok" if ok else "error"
    # Persist status change
    await DB.save_sources(sources)
    _write_config_file()
    return {"ok":ok,"detail":detail}


# ── Web search config ─────────────────────────────────────────────────────────

@app.get("/api/websearch/config")
async def get_websearch_config():
    return asdict(web_cfg)


@app.post("/api/websearch/config")
async def set_websearch_config(req: WebSearchConfigRequest):
    if req.engine        is not None: web_cfg.engine        = req.engine
    if req.result_count  is not None: web_cfg.result_count  = max(1,min(req.result_count,20))
    if req.crawl_depth   is not None: web_cfg.crawl_depth   = max(0,min(req.crawl_depth,3))
    if req.crawl_breadth is not None: web_cfg.crawl_breadth = max(1,min(req.crawl_breadth,10))
    if req.crawl_timeout is not None: web_cfg.crawl_timeout = req.crawl_timeout
    if req.include_archive is not None: web_cfg.include_archive=req.include_archive
    if req.safe_search   is not None: web_cfg.safe_search   = req.safe_search
    await DB.save_web_search_config(web_cfg)
    _write_config_file()
    return asdict(web_cfg)


# ── Models ────────────────────────────────────────────────────────────────────

@app.get("/api/models")
async def get_models():
    return [{"instance":i.name,"tier":i.tier,"host":i.base_url,
             "current_model":i.model,"available":await list_models(i),"enabled":i.enabled}
            for i in instances]


@app.get("/api/config/instances")
async def get_instances_cfg():
    return [{"name":i.name,"host":i.host,"port":i.port,"tier":i.tier,
             "model":i.model,"ctx_size":i.ctx_size,"enabled":i.enabled} for i in instances]


@app.post("/api/config/instances")
async def update_instances(req: InstanceUpdateRequest):
    global instances
    new=[]
    for d in req.instances:
        try:
            new.append(OllamaInstance(name=d["name"],host=d["host"],port=int(d["port"]),
                tier=ModelTier(d["tier"]),model=d["model"],
                ctx_size=int(d.get("ctx_size",8192)),enabled=bool(d.get("enabled",True))))
        except Exception as e: raise HTTPException(400,f"Invalid: {e}")
    instances=new
    await DB.save_instances(instances)
    _write_config_file()
    return {"ok":True,"count":len(instances)}


# ── Projects ──────────────────────────────────────────────────────────────────

@app.post("/api/projects")
async def create_project(req: ProjectCreateRequest):
    proj = Project(id=str(uuid.uuid4())[:12], name=req.name,
                   description=req.description, output_mode=req.output_mode)
    projects[proj.id] = proj
    await DB.save_project(proj)
    return proj.to_dict()


@app.get("/api/projects")
async def list_projects():
    # Merge in-memory with DB (DB is authoritative for persisted ones)
    db_rows = await DB.load_projects()
    db_ids = {r["id"] for r in db_rows}
    mem_only = [p.to_dict() for p in projects.values() if p.id not in db_ids]
    return mem_only + db_rows


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    db_row = await DB.load_project(project_id)
    if db_row:
        return db_row
    p = projects.get(project_id)
    if not p: raise HTTPException(404, "Project not found")
    return {**p.to_dict(), "rounds": [{"id":r.id,"round_num":r.round_num,"query":r.query,
        "created_at":r.created_at} for r in p.rounds], "context_summary":p.context_summary}


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    if project_id not in projects and not await DB.load_project(project_id):
        raise HTTPException(404, "Project not found")
    projects.pop(project_id, None)
    await DB.delete_project(project_id)
    proj_dir = PROJECTS_DIR / project_id
    if proj_dir.exists(): shutil.rmtree(proj_dir)
    return {"ok": True}


@app.get("/api/projects/{project_id}/download")
async def download_project(project_id: str):
    """Zip all generated files for a project — DB first, disk fallback."""
    import io, zipfile
    from fastapi.responses import Response as FR

    # Try DB first
    db_files = await DB.load_generated_files_for_project(project_id)
    proj_name = (projects.get(project_id) or type("P",(),{"name":project_id})()).name

    if db_files:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path, content in db_files.items():
                zf.writestr(path, content)
        buf.seek(0)
        return FR(content=buf.read(), media_type="application/zip",
                  headers={"Content-Disposition":
                           f'attachment; filename="{proj_name.replace(" ","_")}_files.zip"'})

    # Disk fallback
    files_dir = PROJECTS_DIR / project_id / "files"
    if not files_dir.exists():
        raise HTTPException(404, "No generated files for this project")
    zip_path = PROJECTS_DIR / project_id / f"{project_id}.zip"
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", str(files_dir))
    return FileResponse(str(zip_path), media_type="application/zip",
                        filename=f"{proj_name.replace(' ','_')}.zip")


# ── Database ──────────────────────────────────────────────────────────────────

@app.get("/api/db/stats")
async def db_stats():
    return await DB.get_stats()


@app.get("/api/db/search")
async def db_search(
    q:           str = Query(""),
    mode:        str = Query(""),
    output_mode: str = Query(""),
    limit:       int = Query(24, ge=1, le=200),
    offset:      int = Query(0,  ge=0),
):
    """
    Paginated full-text search across all saved research.
    PG: uses tsvector + ts_headline.  SQLite: LIKE fallback.
    Returns {items, total}.
    """
    rows, total = await DB.search(
        q=q, mode=mode, output_mode=output_mode,
        limit=limit, offset=offset,
    )
    return {"items": rows, "total": total}


@app.post("/api/db/export")
async def db_export(payload: dict):
    """Export DB as JSON. Body: {"limit": 500}"""
    limit = int(payload.get("limit", 500))
    return await DB.export_all(limit=limit)



# ── Bookmarks ─────────────────────────────────────────────────────────────────
# In-memory store (persisted via DB.save_bookmark / load_bookmarks)
bookmarks: dict[str, dict] = {}   # id → bookmark dict


@app.get("/api/bookmarks")
async def get_bookmarks():
    rows = await DB.load_bookmarks()
    return rows


@app.post("/api/bookmarks")
async def add_bookmark(payload: dict):
    """
    Bookmark a citation or a whole job result.
    Body: {type: "citation"|"job", job_id, title, url, snippet,
           screenshot_url, source_type, domain, tags:[]}
    """
    bm = {
        "id":             str(uuid.uuid4())[:12],
        "type":           payload.get("type", "citation"),
        "job_id":         payload.get("job_id", ""),
        "title":          payload.get("title", ""),
        "url":            payload.get("url", ""),
        "snippet":        payload.get("snippet", "")[:600],
        "screenshot_url": payload.get("screenshot_url", ""),
        "source_type":    payload.get("source_type", "web"),
        "domain":         payload.get("domain", ""),
        "tags":           payload.get("tags", []),
        "note":           payload.get("note", ""),
        "created_at":     time.time(),
    }
    bookmarks[bm["id"]] = bm
    await DB.save_bookmark(bm)
    return bm


@app.patch("/api/bookmarks/{bm_id}")
async def update_bookmark(bm_id: str, payload: dict):
    """Update note or tags on a bookmark."""
    bm = bookmarks.get(bm_id) or await DB.get_bookmark(bm_id)
    if not bm:
        raise HTTPException(404, "Bookmark not found")
    if "note" in payload: bm["note"] = payload["note"]
    if "tags" in payload: bm["tags"] = payload["tags"]
    bookmarks[bm_id] = bm
    await DB.save_bookmark(bm)
    return bm


@app.delete("/api/bookmarks/{bm_id}")
async def delete_bookmark(bm_id: str):
    bookmarks.pop(bm_id, None)
    await DB.delete_bookmark(bm_id)
    return {"ok": True}


# ── Project: add job / add bookmark ──────────────────────────────────────────

@app.post("/api/projects/{project_id}/add_job")
async def project_add_job(project_id: str, payload: dict):
    """Add an existing completed job to a project (without re-running)."""
    job_id = payload.get("job_id", "")
    proj = projects.get(project_id)
    if not proj:
        db_row = await DB.load_project(project_id)
        if not db_row:
            raise HTTPException(404, "Project not found")
        # Reconstruct minimal project in memory
        proj = Project(
            id=db_row["id"], name=db_row["name"],
            description=db_row.get("description",""),
            output_mode=OutputMode(db_row.get("output_mode","report")),
            context_summary=db_row.get("context_summary",""),
        )
        projects[project_id] = proj

    # Load the job result
    job_data = await DB.load_job_result(job_id)
    if not job_data:
        raise HTTPException(404, "Job not found")

    # Create a round for it
    from dataclasses import fields as dc_fields
    round_ = ProjectRound(
        id=str(uuid.uuid4())[:8],
        job_id=job_id,
        round_num=len(proj.rounds)+1,
        query=job_data.get("query",""),
        result=(job_data.get("result") or "")[:4000],
        citations=job_data.get("citations",[]),
    )
    proj.rounds.append(round_)
    proj.updated_at = time.time()
    # Update context summary
    if not proj.context_summary:
        proj.context_summary = f"Project: {proj.name}\nAdded: {job_data.get('query','')}"
    else:
        proj.context_summary += f"\n\nAdded job: {job_data.get('query','')}"
    await DB.save_project(proj)
    return {"ok": True, "round_num": round_.round_num}


@app.post("/api/projects/{project_id}/add_bookmark")
async def project_add_bookmark(project_id: str, payload: dict):
    """Tag a bookmark as belonging to a project."""
    bm_id = payload.get("bookmark_id","")
    bm = bookmarks.get(bm_id) or await DB.get_bookmark(bm_id)
    if not bm:
        raise HTTPException(404, "Bookmark not found")
    tags = bm.get("tags", [])
    tag = f"project:{project_id}"
    if tag not in tags:
        tags.append(tag)
        bm["tags"] = tags
        bookmarks[bm_id] = bm
        await DB.save_bookmark(bm)
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════════
#  Notebook API
# ══════════════════════════════════════════════════════════════════════════════

notebooks_cache:  dict[str, dict]          = {}
cell_ws_clients:  dict[str, list[WebSocket]]= {}


class NotebookCreateRequest(BaseModel):
    title:       str = "Untitled Notebook"
    description: str = ""
    project_id:  Optional[str] = None
    tags:        list[str] = Field(default_factory=list)

class CellCreateRequest(BaseModel):
    cell_type:  str = "markdown"
    lang:       str = "python"
    tag:        str = "none"
    content:    str = ""
    sort_order: int = 0

class CellUpdateRequest(BaseModel):
    content:    Optional[str] = None
    cell_type:  Optional[str] = None
    lang:       Optional[str] = None
    tag:        Optional[str] = None
    generated:  Optional[str] = None
    sort_order: Optional[int] = None

class CellChatRequest(BaseModel):
    message: str
    mode:    str = "chat"

class ReorderRequest(BaseModel):
    order: list[str]


@app.post("/api/notebooks")
async def create_notebook(req: NotebookCreateRequest):
    nb = {"id":str(uuid.uuid4())[:16],"title":req.title,"description":req.description,
          "project_id":req.project_id,"tags":req.tags,"cells":[],
          "created_at":time.time(),"updated_at":time.time()}
    await DB.save_notebook(nb); notebooks_cache[nb["id"]]=nb; return nb


@app.get("/api/notebooks")
async def list_notebooks(project_id: Optional[str] = None):
    return await DB.load_notebooks(project_id)


@app.get("/api/notebooks/{nb_id}")
async def get_notebook(nb_id: str):
    nb = await DB.load_notebook(nb_id)
    if not nb: raise HTTPException(404,"Notebook not found")
    return nb


@app.patch("/api/notebooks/{nb_id}")
async def update_notebook_meta(nb_id: str, payload: dict):
    nb = await DB.load_notebook(nb_id)
    if not nb: raise HTTPException(404,"Notebook not found")
    for k in ("title","description","tags"):
        if k in payload: nb[k] = payload[k]
    nb["updated_at"] = time.time()
    await DB.save_notebook(nb); return nb


@app.delete("/api/notebooks/{nb_id}")
async def delete_notebook_route(nb_id: str):
    await DB.delete_notebook(nb_id); notebooks_cache.pop(nb_id,None); return {"ok":True}


@app.post("/api/notebooks/{nb_id}/cells")
async def add_cell(nb_id: str, req: CellCreateRequest):
    cell = {"id":str(uuid.uuid4())[:16],"notebook_id":nb_id,
            "sort_order":req.sort_order,"cell_type":req.cell_type,"lang":req.lang,
            "tag":req.tag,"content":req.content,"generated":"","thread":[],
            "created_at":time.time(),"updated_at":time.time()}
    await DB.save_cell(cell); return cell


@app.patch("/api/notebooks/{nb_id}/cells/{cell_id}")
async def update_cell(nb_id: str, cell_id: str, req: CellUpdateRequest):
    cell = await DB.load_cell(cell_id)
    if not cell: raise HTTPException(404,"Cell not found")
    for k,v in req.model_dump(exclude_none=True).items(): cell[k]=v
    cell["updated_at"]=time.time()
    await DB.save_cell(cell); return cell


@app.delete("/api/notebooks/{nb_id}/cells/{cell_id}")
async def delete_cell_route(nb_id: str, cell_id: str):
    await DB.delete_cell(cell_id); return {"ok":True}


@app.post("/api/notebooks/{nb_id}/reorder")
async def reorder_cells(nb_id: str, req: ReorderRequest):
    for i,cid in enumerate(req.order):
        c = await DB.load_cell(cid)
        if c and c["notebook_id"]==nb_id:
            c["sort_order"]=i; c["updated_at"]=time.time()
            await DB.save_cell(c)
    return {"ok":True}


# ── Page endpoints ──────────────────────────────────────────────────────────

@app.get("/api/notebooks/{nb_id}/pages")
async def list_pages(nb_id: str):
    return await DB.load_pages(nb_id)

@app.post("/api/notebooks/{nb_id}/pages")
async def create_page(nb_id: str, req: PageCreateRequest):
    nb = await DB.load_notebook(nb_id)
    if not nb: raise HTTPException(404,"Notebook not found")
    page = {"id":str(uuid.uuid4())[:16],"notebook_id":nb_id,
            "title":req.title,"sort_order":req.sort_order,
            "created_at":time.time(),"updated_at":time.time()}
    await DB.save_page(page); return page

@app.patch("/api/notebooks/{nb_id}/pages/{page_id}")
async def update_page(nb_id: str, page_id: str, payload: dict):
    pages = await DB.load_pages(nb_id)
    page = next((p for p in pages if p["id"]==page_id), None)
    if not page: raise HTTPException(404,"Page not found")
    for k in ("title","sort_order"):
        if k in payload: page[k] = payload[k]
    page["updated_at"] = time.time()
    await DB.save_page(page); return page

@app.delete("/api/notebooks/{nb_id}/pages/{page_id}")
async def delete_page_ep(nb_id: str, page_id: str):
    await DB.delete_page(page_id); return {"ok":True}

@app.post("/api/notebooks/{nb_id}/cells/{cell_id}/name")
async def auto_name_cell(nb_id: str, cell_id: str):
    """Ask the Writer to suggest a short title for this cell."""
    cell = await DB.load_cell(cell_id)
    if not cell: raise HTTPException(404,"Cell not found")
    raw = (cell.get("content","") + "\n" + cell.get("generated","")).strip()
    if not raw: return {"title":""}
    if len(raw) <= 1200:
        excerpt = raw[:1200]
    else:
        mid = len(raw)//2
        excerpt = raw[:600] + "\n...\n" + raw[mid:mid+400]
    writer = await get_instance(ModelTier.WRITER) or await get_instance(ModelTier.THINKER)
    if not writer: return {"title":""}
    title = await collect_ollama(writer, excerpt,
        "Generate a very short descriptive title (3-7 words) for this notebook cell. "
        "Respond with ONLY the title, no quotes, no punctuation at end, no preamble.",
        cell_id, timeout_secs=45)
    title = title.strip().strip('"').strip("'").splitlines()[0][:80]
    cell["title"] = title; cell["updated_at"] = time.time()
    await DB.save_cell(cell)
    return {"title": title}


@app.post("/api/notebooks/from_job/{job_id}")
async def notebook_from_job(job_id: str, payload: dict):
    """Create a notebook pre-populated from a completed research job."""
    job_data = await DB.load_job_result(job_id)
    if not job_data: raise HTTPException(404,"Job not found")
    title = payload.get("title") or (job_data.get("query","Research")[:80])
    nb = {"id":str(uuid.uuid4())[:16],"title":title,
          "description":f"Compiled from job {job_id[:8]}",
          "project_id":payload.get("project_id"),"tags":["research"],
          "cells":[],"created_at":time.time(),"updated_at":time.time()}
    await DB.save_notebook(nb)
    cells=[]
    def _cell(order,ctype,content,lang="python",tag="none"):
        return {"id":str(uuid.uuid4())[:16],"notebook_id":nb["id"],"sort_order":order,
                "cell_type":ctype,"lang":lang,"tag":tag,"content":content,
                "generated":"","thread":[],"created_at":time.time(),"updated_at":time.time()}
    cells.append(_cell(0,"markdown",f"# {title}"))
    if job_data.get("result"):
        cells.append(_cell(1,"markdown",job_data["result"][:12000]))
    cits=job_data.get("citations",[])
    if cits:
        src="## Sources\n\n"+"\n".join(f"- [{c.get('title',c.get('url',''))}]({c.get('url','')})  \n  {c.get('snippet','')[:100]}" for c in cits[:20])
        cells.append(_cell(2,"markdown",src))
    for i,f in enumerate(job_data.get("file_manifest",[])[:8]):
        content=await DB.get_generated_file(job_id,f["file_path"])
        if content:
            ext=Path(f["file_path"]).suffix.lstrip(".")
            cells.append(_cell(3+i,"code",content[:8000],lang=ext or "text"))
    for c in cells: await DB.save_cell(c)
    nb["cells"]=cells; return nb


def _build_nb_context(nb: dict, current_cell: dict) -> str:
    cells = sorted(nb.get("cells",[]), key=lambda c: c.get("sort_order",0))
    parts = [f"Notebook: {nb['title']}"]
    if nb.get("description"): parts.append(f"Description: {nb['description']}")
    for c in cells:
        if c["id"]==current_cell["id"]: break
        txt=(c.get("generated") or c.get("content",""))[:400]
        if txt.strip():
            m=f"[{c['cell_type'].upper()}{':'+c['lang'] if c['cell_type']=='code' else ''}]"
            parts.append(f"{m} {txt}")
    return "\n\n".join(parts)


async def _cell_broadcast(cell_id: str, payload: dict):
    msg=json.dumps(payload)
    for ws in list(cell_ws_clients.get(cell_id,[])):
        try: await ws.send_text(msg)
        except Exception:
            try: cell_ws_clients[cell_id].remove(ws)
            except ValueError: pass


async def _do_generate(nb: dict, cell: dict, nb_ctx: str) -> str:
    tag=cell.get("tag","none"); content=cell.get("content","").strip()
    cid=cell["id"]
    if not content:
        await _cell_broadcast(cid,{"type":"error","text":"Cell is empty"}); return ""
    if tag=="to_code":
        sys_p="You are an expert programmer. Convert the description to complete, working code. Add comments."
        prompt=f"{nb_ctx}\n\nConvert to {cell.get('lang','python')}:\n{content}"
    elif tag=="summarise":
        sys_p="You are a technical writer. Summarise concisely, preserve key facts."
        prompt=f"{nb_ctx}\n\nSummarise:\n{content}"
    elif tag=="research":
        return await _do_research(nb,cell,nb_ctx,content)
    else:
        if cell.get("cell_type")=="code":
            sys_p="You are an expert programmer. Write complete, working code with comments."
            prompt=f"{nb_ctx}\n\nWrite {cell.get('lang','python')} code for:\n{content}"
        else:
            sys_p=("You are a knowledgeable assistant. Flesh out the user's brief note into a thorough, "
                   "well-structured response. Use markdown headings and bullet points.")
            prompt=f"{nb_ctx}\n\nFlesh out this note into a complete section:\n\n{content}"
    writer=await get_instance(ModelTier.WRITER) or await get_instance(ModelTier.THINKER)
    if not writer: await _cell_broadcast(cid,{"type":"error","text":"No model available"}); return ""
    parts=[]
    async for tok in stream_ollama(writer,prompt,sys_p,f"cell:{cid}",timeout_secs=WRITER_TIMEOUT):
        parts.append(tok); await _cell_broadcast(cid,{"type":"token","text":tok})
    generated="".join(parts)
    cell["generated"]=generated
    t=cell.get("thread",[]); t.append({"role":"assistant","content":generated,"action":"generate","t":time.time()})
    cell["thread"]=t; cell["updated_at"]=time.time()
    await DB.save_cell(cell)
    await _cell_broadcast(cid,{"type":"done","generated":generated,"cell_id":cid})
    return generated


async def _do_research(nb: dict, cell: dict, nb_ctx: str, query: str) -> str:
    cid=cell["id"]
    await _cell_broadcast(cid,{"type":"status","text":"Researching…"})
    ctx_str=""; cits: list[Citation] = []
    try:
        # Use gather_all_sources so all configured sources (web, neo4j, chroma, etc.) are queried
        class _FJ:
            id="nb"
            sources=[]
            citations: list = []
        fake_job=_FJ()
        cits, ctx_str = await gather_all_sources(query, fake_job)  # type: ignore
        if not cits:
            # fallback to web search only
            cits = await gather_web_search(query, fake_job)
            ctx_str = "\n\n".join(
                f"[{i+1}] {c.title}\n{c.snippet[:300]}" for i,c in enumerate(cits[:8])
            )
        # Broadcast citations so the frontend Sources tab and research sidebar populate
        await _cell_broadcast(cid,{
            "type": "citations",
            "citations": [c.to_dict() for c in cits[:20]]
        })
    except Exception as e:
        log.debug("nb research gather: %s", e)
    writer=await get_instance(ModelTier.WRITER) or await get_instance(ModelTier.THINKER)
    if not writer: await _cell_broadcast(cid,{"type":"error","text":"No model"}); return ""
    sys_p=("You are a research assistant writing for a notebook. Use the provided sources. "
           "Cite inline as [1],[2] etc. Use ## headings and bullet points for structure.")
    prompt=f"{nb_ctx}\n\nQuery: {query}\n\nSources:\n{ctx_str[:4000]}\n\nWrite a comprehensive, well-cited notebook section."
    parts=[]
    async for tok in stream_ollama(writer,prompt,sys_p,f"cell:{cid}",timeout_secs=WRITER_TIMEOUT):
        parts.append(tok); await _cell_broadcast(cid,{"type":"token","text":tok})
    generated="".join(parts)
    cell["generated"]=generated
    # Store citations on the cell for persistence
    cell["citations"]=[c.to_dict() for c in cits[:20]]
    t=cell.get("thread",[]); t.append({"role":"assistant","content":generated,"action":"research","t":time.time()})
    cell["thread"]=t; cell["updated_at"]=time.time()
    await DB.save_cell(cell)
    await _cell_broadcast(cid,{"type":"done","generated":generated,"cell_id":cid,"citations":[c.to_dict() for c in cits[:20]]})
    return generated


async def _do_chat(nb: dict, cell: dict, nb_ctx: str, message: str) -> str:
    cid=cell["id"]
    writer=await get_instance(ModelTier.WRITER) or await get_instance(ModelTier.THINKER)
    if not writer: await _cell_broadcast(cid,{"type":"error","text":"No model"}); return ""
    thread=cell.get("thread",[]); hist="\n".join(
        f"{'User' if m['role']=='user' else 'Assistant'}: {m['content'][:400]}" for m in thread[-6:])
    sys_p="You are a helpful notebook assistant. Be concise. You can suggest edits, explain, write code, answer questions."
    prompt=f"{nb_ctx}\n\nCell content:\n{(cell.get('generated') or cell.get('content',''))[:2000]}\n\nConversation:\n{hist}\n\nUser: {message}\nAssistant:"
    parts=[]
    async for tok in stream_ollama(writer,prompt,sys_p,f"cell:{cid}",timeout_secs=WRITER_TIMEOUT):
        parts.append(tok); await _cell_broadcast(cid,{"type":"token","text":tok})
    resp="".join(parts)
    thread.append({"role":"user","content":message,"t":time.time()})
    thread.append({"role":"assistant","content":resp,"action":"chat","t":time.time()})
    cell["thread"]=thread; cell["updated_at"]=time.time()
    await DB.save_cell(cell)
    await _cell_broadcast(cid,{"type":"done","response":resp,"cell_id":cid,"thread":thread})
    return resp


@app.websocket("/ws/notebook/{nb_id}/cell/{cell_id}")
async def cell_stream_ws(ws: WebSocket, nb_id: str, cell_id: str):
    await ws.accept()
    cell_ws_clients.setdefault(cell_id,[]).append(ws)
    try:
        while True:
            raw=await ws.receive_text()
            try: req=json.loads(raw)
            except Exception: continue
            action=req.get("action","generate"); message=req.get("message","")
            nb=await DB.load_notebook(nb_id); cell=await DB.load_cell(cell_id)
            if not nb or not cell:
                await _cell_broadcast(cell_id,{"type":"error","text":"Not found"}); continue
            nb_ctx=_build_nb_context(nb,cell)
            if action=="generate": await _do_generate(nb,cell,nb_ctx)
            elif action=="research": await _do_research(nb,cell,nb_ctx,message or cell.get("content",""))
            elif action=="chat": await _do_chat(nb,cell,nb_ctx,message)
    except WebSocketDisconnect: pass
    finally:
        try: cell_ws_clients.get(cell_id,[]).remove(ws)
        except ValueError: pass


@app.post("/api/notebooks/{nb_id}/cells/{cell_id}/chat")
async def cell_chat_rest(nb_id: str, cell_id: str, req: CellChatRequest):
    nb=await DB.load_notebook(nb_id); cell=await DB.load_cell(cell_id)
    if not nb or not cell: raise HTTPException(404,"Not found")
    nb_ctx=_build_nb_context(nb,cell)
    if req.mode=="research": resp=await _do_research(nb,cell,nb_ctx,req.message)
    else: resp=await _do_chat(nb,cell,nb_ctx,req.message)
    cell_upd=await DB.load_cell(cell_id)
    return {"response":resp,"thread":cell_upd.get("thread",[]) if cell_upd else []}


@app.websocket("/ws/stream/{job_id}")
async def ws_stream(ws: WebSocket, job_id: str):
    await ws.accept()
    ws_clients.setdefault(job_id, []).append(ws)
    try:
        while True: await ws.receive_text()
    except WebSocketDisconnect: pass
    finally:
        try: ws_clients.get(job_id,[]).remove(ws)
        except ValueError: pass

@app.get("/api/debug/screenshot")
async def debug_screenshot(url: str = Query("https://example.com")):
    """Test screenshot capture with full diagnostics."""
    import sys, importlib
    result = {
        "url": url,
        "playwright_importable": False,
        "playwright_version": None,
        "browser_launched": False,
        "browser_error": None,
        "screenshot_attempted": False,
        "screenshot_result": None,
        "screenshot_error": None,
        "fallback_used": None,
        "file_written": False,
        "file_path": None,
    }

    # Check playwright import
    try:
        import playwright
        result["playwright_importable"] = True
        result["playwright_version"] = getattr(playwright, "__version__", "unknown")
    except ImportError as e:
        result["browser_error"] = f"playwright not installed: {e}"
        return result

    # Check browser
    try:
        browser = await _get_browser()
        result["browser_launched"] = browser is not None and browser.is_connected()
    except Exception as e:
        result["browser_error"] = str(e)

    # Attempt full screenshot
    try:
        result["screenshot_attempted"] = True
        path = await capture_screenshot(url)
        result["screenshot_result"] = path
        full = SCREENSHOT_DIR / path
        result["file_written"] = full.exists()
        result["file_path"] = str(full)
        result["fallback_used"] = path.endswith(".svg")
    except Exception as e:
        result["screenshot_error"] = str(e)

    return result
# ══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    module_name = __spec__.name if __spec__ is not None else "researcher_api"
    reload_dir  = os.path.dirname(os.path.abspath(__file__))
    uvicorn.run(f"{module_name}:app", host="0.0.0.0", port=8765,
                reload=True, reload_dirs=[reload_dir], log_level="info")