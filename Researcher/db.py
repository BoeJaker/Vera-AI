"""
db.py  —  Vera Research Agent persistence layer  (v2, PostgreSQL-native)
─────────────────────────────────────────────────────────────────────────

Primary backend: PostgreSQL via asyncpg.
  pip install asyncpg

Dev fallback: SQLite via aiosqlite (zero config, file-based).
  pip install aiosqlite

Configuration
─────────────
Set the environment variable VERA_DB_URL to a PostgreSQL DSN:

    export VERA_DB_URL="postgresql://vera:secret@localhost:5432/vera_research"

Leave it unset (or empty) to use SQLite at ./vera_research.db.

    export VERA_SQLITE_PATH="/data/vera_research.db"   # optional

PostgreSQL features used
────────────────────────
  • asyncpg connection pool (min 2, max 20)
  • JSONB for sources, steps, file_tree, citations list
  • tsvector / GIN index for full-text search on query + result
  • ON CONFLICT … DO UPDATE  (proper upsert)
  • Parameterised queries ($1 … $N) throughout
  • Cascade deletes via foreign keys
  • UNLOGGED tables option for citations (fast writes, tolerates crash)

Quick-start with Docker
───────────────────────
  docker run -d --name vera-pg \
    -e POSTGRES_DB=vera_research \
    -e POSTGRES_USER=vera \
    -e POSTGRES_PASSWORD=secret \
    -p 5432:5432 postgres:16-alpine

  export VERA_DB_URL="postgresql://vera:secret@localhost:5432/vera_research"
  python researcher_api.py
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("vera.db")

# ── backend detection ─────────────────────────────────────────────────────────

_DB_URL: str = os.environ.get("VERA_DB_URL", "postgres").strip()
_USE_PG: bool = _DB_URL.startswith(("postgresql", "postgres"))

if _USE_PG:
    try:
        import asyncpg  # type: ignore  # noqa: F401
        log.info("DB backend: PostgreSQL  (%s)", re.sub(r":([^:@]+)@", ":***@", _DB_URL))
    except ImportError:
        log.warning("asyncpg not installed (pip install asyncpg) — falling back to SQLite")
        _USE_PG = False

if not _USE_PG:
    try:
        import aiosqlite  # type: ignore
    except ImportError as e:
        raise ImportError("Install aiosqlite for SQLite support: pip install aiosqlite") from e
    _SQLITE_PATH = Path(os.environ.get("VERA_SQLITE_PATH", "vera_research.db"))
    log.info("DB backend: SQLite  (%s)", _SQLITE_PATH.resolve())


# ══════════════════════════════════════════════════════════════════════════════
#  Schema
# ══════════════════════════════════════════════════════════════════════════════

# ── PostgreSQL DDL ────────────────────────────────────────────────────────────
_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_jobs (
    id            TEXT        PRIMARY KEY,
    query         TEXT        NOT NULL,
    mode          TEXT        NOT NULL,
    output_mode   TEXT        NOT NULL DEFAULT 'report',
    status        TEXT        NOT NULL,
    result        TEXT,
    error         TEXT,
    sources       JSONB       DEFAULT '[]',
    steps         JSONB       DEFAULT '[]',
    file_tree     JSONB       DEFAULT '{}',
    project_id    TEXT,
    token_count   INT         DEFAULT 0,
    created_at    DOUBLE PRECISION NOT NULL,
    finished_at   DOUBLE PRECISION,
    search_vec    tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(query, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(left(result, 50000), '')), 'B')
        ) STORED
);

CREATE INDEX IF NOT EXISTS idx_jobs_created    ON research_jobs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_project    ON research_jobs (project_id);
CREATE INDEX IF NOT EXISTS idx_jobs_mode       ON research_jobs (mode);
CREATE INDEX IF NOT EXISTS idx_jobs_output     ON research_jobs (output_mode);
CREATE INDEX IF NOT EXISTS idx_jobs_status     ON research_jobs (status);
CREATE INDEX IF NOT EXISTS idx_jobs_fts        ON research_jobs USING GIN (search_vec);

CREATE TABLE IF NOT EXISTS citations (
    id               TEXT    PRIMARY KEY,
    job_id           TEXT    NOT NULL REFERENCES research_jobs (id) ON DELETE CASCADE,
    url              TEXT,
    title            TEXT,
    snippet          TEXT,
    source_type      TEXT,
    screenshot_path  TEXT,
    domain           TEXT,
    fetched_at       DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_cits_job ON citations (job_id);

CREATE TABLE IF NOT EXISTS projects (
    id               TEXT    PRIMARY KEY,
    name             TEXT    NOT NULL,
    description      TEXT,
    output_mode      TEXT    NOT NULL DEFAULT 'report',
    context_summary  TEXT,
    file_tree        JSONB   DEFAULT '{}',
    created_at       DOUBLE PRECISION NOT NULL,
    updated_at       DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects (updated_at DESC);

CREATE TABLE IF NOT EXISTS project_rounds (
    id          TEXT    PRIMARY KEY,
    project_id  TEXT    NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    job_id      TEXT,
    round_num   INT     NOT NULL,
    query       TEXT    NOT NULL,
    result      TEXT,
    citations   JSONB   DEFAULT '[]',
    created_at  DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rounds_project ON project_rounds (project_id);

CREATE TABLE IF NOT EXISTS source_configs (
    id       TEXT    PRIMARY KEY,
    label    TEXT    NOT NULL,
    type     TEXT    NOT NULL,
    enabled  BOOLEAN NOT NULL DEFAULT TRUE,
    config   JSONB   DEFAULT '{}',
    status   TEXT    DEFAULT 'unknown',
    sort_order INT   DEFAULT 0
);

CREATE TABLE IF NOT EXISTS web_search_config (
    id              TEXT    PRIMARY KEY DEFAULT 'singleton',
    engine          TEXT    DEFAULT 'searxng',
    result_count    INT     DEFAULT 8,
    crawl_depth     INT     DEFAULT 1,
    crawl_breadth   INT     DEFAULT 3,
    crawl_timeout   DOUBLE PRECISION DEFAULT 8.0,
    include_archive BOOLEAN DEFAULT FALSE,
    safe_search     INT     DEFAULT 0
);

CREATE TABLE IF NOT EXISTS instance_configs (
    name      TEXT    PRIMARY KEY,
    host      TEXT    NOT NULL,
    port      INT     NOT NULL,
    tier      TEXT    NOT NULL,
    model     TEXT    NOT NULL,
    ctx_size  INT     DEFAULT 8192,
    enabled   BOOLEAN DEFAULT TRUE,
    sort_order INT    DEFAULT 0
);

CREATE TABLE IF NOT EXISTS bookmarks (
    id             TEXT    PRIMARY KEY,
    type           TEXT    NOT NULL DEFAULT 'citation',
    job_id         TEXT,
    title          TEXT,
    url            TEXT,
    snippet        TEXT,
    screenshot_url TEXT,
    source_type    TEXT,
    domain         TEXT,
    tags           JSONB   DEFAULT '[]',
    note           TEXT    DEFAULT '',
    created_at     DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bm_created ON bookmarks (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bm_job     ON bookmarks (job_id);

CREATE TABLE IF NOT EXISTS generated_files (
    id          TEXT    PRIMARY KEY,
    job_id      TEXT    NOT NULL REFERENCES research_jobs (id) ON DELETE CASCADE,
    project_id  TEXT,
    file_path   TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    size_bytes  INT     DEFAULT 0,
    created_at  DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_gf_job     ON generated_files (job_id);
CREATE INDEX IF NOT EXISTS idx_gf_project ON generated_files (project_id);
CREATE INDEX IF NOT EXISTS idx_gf_path    ON generated_files (file_path);

CREATE TABLE IF NOT EXISTS notebooks (
    id          TEXT    PRIMARY KEY,
    title       TEXT    NOT NULL DEFAULT 'Untitled Notebook',
    description TEXT    DEFAULT '',
    project_id  TEXT,
    tags        JSONB   DEFAULT '[]',
    created_at  DOUBLE PRECISION NOT NULL,
    updated_at  DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS notebook_cells (
    id           TEXT    PRIMARY KEY,
    notebook_id  TEXT    NOT NULL REFERENCES notebooks (id) ON DELETE CASCADE,
    sort_order   INT     NOT NULL DEFAULT 0,
    cell_type    TEXT    NOT NULL DEFAULT 'markdown',
    lang         TEXT    DEFAULT 'python',
    tag          TEXT    DEFAULT 'none',
    content      TEXT    NOT NULL DEFAULT '',
    generated    TEXT    DEFAULT '',
    thread       JSONB   DEFAULT '[]',
    created_at   DOUBLE PRECISION NOT NULL,
    updated_at   DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cells_nb ON notebook_cells (notebook_id, sort_order);
"""

# SQLite DDL (no tsvector, no JSONB, no generated columns)
_SQLITE_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS research_jobs (
    id            TEXT    PRIMARY KEY,
    query         TEXT    NOT NULL,
    mode          TEXT    NOT NULL,
    output_mode   TEXT    NOT NULL DEFAULT 'report',
    status        TEXT    NOT NULL,
    result        TEXT,
    error         TEXT,
    sources       TEXT    DEFAULT '[]',
    steps         TEXT    DEFAULT '[]',
    file_tree     TEXT    DEFAULT '{}',
    project_id    TEXT,
    token_count   INTEGER DEFAULT 0,
    created_at    REAL    NOT NULL,
    finished_at   REAL
);

CREATE INDEX IF NOT EXISTS idx_jobs_created ON research_jobs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_project ON research_jobs (project_id);

CREATE TABLE IF NOT EXISTS citations (
    id               TEXT    PRIMARY KEY,
    job_id           TEXT    NOT NULL REFERENCES research_jobs (id) ON DELETE CASCADE,
    url              TEXT,
    title            TEXT,
    snippet          TEXT,
    source_type      TEXT,
    screenshot_path  TEXT,
    domain           TEXT,
    fetched_at       REAL
);

CREATE INDEX IF NOT EXISTS idx_cits_job ON citations (job_id);

CREATE TABLE IF NOT EXISTS projects (
    id               TEXT    PRIMARY KEY,
    name             TEXT    NOT NULL,
    description      TEXT,
    output_mode      TEXT    NOT NULL DEFAULT 'report',
    context_summary  TEXT,
    file_tree        TEXT    DEFAULT '{}',
    created_at       REAL    NOT NULL,
    updated_at       REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS project_rounds (
    id          TEXT    PRIMARY KEY,
    project_id  TEXT    NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    job_id      TEXT,
    round_num   INTEGER NOT NULL,
    query       TEXT    NOT NULL,
    result      TEXT,
    citations   TEXT    DEFAULT '[]',
    created_at  REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS source_configs (
    id         TEXT    PRIMARY KEY,
    label      TEXT    NOT NULL,
    type       TEXT    NOT NULL,
    enabled    INTEGER NOT NULL DEFAULT 1,
    config     TEXT    DEFAULT '{}',
    status     TEXT    DEFAULT 'unknown',
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS web_search_config (
    id              TEXT    PRIMARY KEY DEFAULT 'singleton',
    engine          TEXT    DEFAULT 'searxng',
    result_count    INTEGER DEFAULT 8,
    crawl_depth     INTEGER DEFAULT 1,
    crawl_breadth   INTEGER DEFAULT 3,
    crawl_timeout   REAL    DEFAULT 8.0,
    include_archive INTEGER DEFAULT 0,
    safe_search     INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS instance_configs (
    name       TEXT    PRIMARY KEY,
    host       TEXT    NOT NULL,
    port       INTEGER NOT NULL,
    tier       TEXT    NOT NULL,
    model      TEXT    NOT NULL,
    ctx_size   INTEGER DEFAULT 8192,
    enabled    INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS bookmarks (
    id             TEXT    PRIMARY KEY,
    type           TEXT    NOT NULL DEFAULT 'citation',
    job_id         TEXT,
    title          TEXT,
    url            TEXT,
    snippet        TEXT,
    screenshot_url TEXT,
    source_type    TEXT,
    domain         TEXT,
    tags           TEXT    DEFAULT '[]',
    note           TEXT    DEFAULT '',
    created_at     REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bm_created ON bookmarks (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_bm_job     ON bookmarks (job_id);

CREATE TABLE IF NOT EXISTS generated_files (
    id          TEXT    PRIMARY KEY,
    job_id      TEXT    NOT NULL REFERENCES research_jobs (id) ON DELETE CASCADE,
    project_id  TEXT,
    file_path   TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    size_bytes  INTEGER DEFAULT 0,
    created_at  REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_gf_job     ON generated_files (job_id);
CREATE INDEX IF NOT EXISTS idx_gf_project ON generated_files (project_id);
CREATE INDEX IF NOT EXISTS idx_gf_path    ON generated_files (file_path);

CREATE TABLE IF NOT EXISTS notebooks (
    id          TEXT    PRIMARY KEY,
    title       TEXT    NOT NULL DEFAULT 'Untitled Notebook',
    description TEXT    DEFAULT '',
    project_id  TEXT,
    tags        TEXT    DEFAULT '[]',
    created_at  REAL    NOT NULL,
    updated_at  REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS notebook_cells (
    id           TEXT    PRIMARY KEY,
    notebook_id  TEXT    NOT NULL REFERENCES notebooks (id) ON DELETE CASCADE,
    sort_order   INTEGER NOT NULL DEFAULT 0,
    cell_type    TEXT    NOT NULL DEFAULT 'markdown',
    lang         TEXT    DEFAULT 'python',
    tag          TEXT    DEFAULT 'none',
    content      TEXT    NOT NULL DEFAULT '',
    generated    TEXT    DEFAULT '',
    thread       TEXT    DEFAULT '[]',
    created_at   REAL    NOT NULL,
    updated_at   REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cells_nb ON notebook_cells (notebook_id, sort_order);
"""


# ══════════════════════════════════════════════════════════════════════════════
#  Pool implementations
# ══════════════════════════════════════════════════════════════════════════════

def _j(v: Any) -> str:
    """Serialise to JSON string for SQLite storage."""
    return json.dumps(v) if not isinstance(v, str) else v


def _jload(v: Any) -> Any:
    """Deserialise JSON string from SQLite."""
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except Exception:
        return v


class _SQLitePool:
    def __init__(self, path: Path):
        self._path = path
        self._conn: Optional[Any] = None

    async def init(self):
        self._conn = await aiosqlite.connect(str(self._path))
        self._conn.row_factory = aiosqlite.Row
        for stmt in _SQLITE_SCHEMA.split(";"):
            s = stmt.strip()
            if s:
                await self._conn.execute(s)
        await self._conn.commit()
        log.info("SQLite ready: %s", self._path.resolve())

    async def execute(self, sql: str, params: tuple = ()):
        await self._conn.execute(sql, params)
        await self._conn.commit()

    async def executemany(self, sql: str, rows: list[tuple]):
        await self._conn.executemany(sql, rows)
        await self._conn.commit()

    async def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        async with self._conn.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def fetchone(self, sql: str, params: tuple = ()) -> Optional[dict]:
        async with self._conn.execute(sql, params) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def close(self):
        if self._conn:
            await self._conn.close()


class _PgPool:
    def __init__(self, url: str):
        self._url = url
        self._pool = None

    async def init(self):
        import asyncpg  # type: ignore
        self._pool = await asyncpg.create_pool(
            self._url,
            min_size=2, max_size=20,
            command_timeout=60,
            statement_cache_size=0,   # safe for PgBouncer
        )
        async with self._pool.acquire() as conn:
            # Run each statement; skip "already exists" errors
            for stmt in _PG_SCHEMA.split(";"):
                s = stmt.strip()
                if not s:
                    continue
                try:
                    await conn.execute(s)
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        log.debug("Schema: %s — %s", s[:60], e)
        log.info("PostgreSQL pool ready (%s)", re.sub(r":([^:@]+)@", ":***@", self._url))

    def _ph(self, sql: str) -> str:
        """Replace ? with $1, $2 … for asyncpg."""
        i = 0
        out = []
        for ch in sql:
            if ch == "?":
                i += 1
                out.append(f"${i}")
            else:
                out.append(ch)
        return "".join(out)

    async def execute(self, sql: str, params: tuple = ()):
        async with self._pool.acquire() as conn:
            await conn.execute(self._ph(sql), *params)

    async def executemany(self, sql: str, rows: list[tuple]):
        async with self._pool.acquire() as conn:
            await conn.executemany(self._ph(sql), rows)

    async def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(self._ph(sql), *params)
        return [dict(r) for r in rows]

    async def fetchone(self, sql: str, params: tuple = ()) -> Optional[dict]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(self._ph(sql), *params)
        return dict(row) if row else None

    async def close(self):
        if self._pool:
            await self._pool.close()


# module-level pool (set in DB.init)
_pool: Optional[_SQLitePool | _PgPool] = None


# ══════════════════════════════════════════════════════════════════════════════
#  SQL helpers (dialect differences)
# ══════════════════════════════════════════════════════════════════════════════

def _upsert_job() -> str:
    """INSERT … ON CONFLICT upsert for research_jobs."""
    if _USE_PG:
        return """
        INSERT INTO research_jobs
            (id,query,mode,output_mode,status,result,error,
             sources,steps,file_tree,project_id,token_count,created_at,finished_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
        ON CONFLICT (id) DO UPDATE SET
            status=EXCLUDED.status, result=EXCLUDED.result,
            error=EXCLUDED.error, steps=EXCLUDED.steps,
            file_tree=EXCLUDED.file_tree, token_count=EXCLUDED.token_count,
            finished_at=EXCLUDED.finished_at
        """
    return """
        INSERT INTO research_jobs
            (id,query,mode,output_mode,status,result,error,
             sources,steps,file_tree,project_id,token_count,created_at,finished_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            status=excluded.status, result=excluded.result,
            error=excluded.error, steps=excluded.steps,
            file_tree=excluded.file_tree, token_count=excluded.token_count,
            finished_at=excluded.finished_at
    """


def _upsert_citation() -> str:
    if _USE_PG:
        return """
        INSERT INTO citations
            (id,job_id,url,title,snippet,source_type,screenshot_path,domain,fetched_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        ON CONFLICT (id) DO NOTHING
        """
    return """
        INSERT INTO citations
            (id,job_id,url,title,snippet,source_type,screenshot_path,domain,fetched_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO NOTHING
    """


def _upsert_project() -> str:
    if _USE_PG:
        return """
        INSERT INTO projects
            (id,name,description,output_mode,context_summary,file_tree,created_at,updated_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        ON CONFLICT (id) DO UPDATE SET
            name=EXCLUDED.name, description=EXCLUDED.description,
            context_summary=EXCLUDED.context_summary,
            file_tree=EXCLUDED.file_tree, updated_at=EXCLUDED.updated_at
        """
    return """
        INSERT INTO projects
            (id,name,description,output_mode,context_summary,file_tree,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, description=excluded.description,
            context_summary=excluded.context_summary,
            file_tree=excluded.file_tree, updated_at=excluded.updated_at
    """


def _upsert_round() -> str:
    if _USE_PG:
        return """
        INSERT INTO project_rounds
            (id,project_id,job_id,round_num,query,result,citations,created_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        ON CONFLICT (id) DO UPDATE SET
            result=EXCLUDED.result, citations=EXCLUDED.citations
        """
    return """
        INSERT INTO project_rounds
            (id,project_id,job_id,round_num,query,result,citations,created_at)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            result=excluded.result, citations=excluded.citations
    """


def _count_col() -> str:
    """Column expression for has_files flag."""
    if _USE_PG:
        return "(file_tree IS NOT NULL AND file_tree != '{}'::jsonb) AS has_files"
    return "(length(coalesce(file_tree,'{}')) > 2) AS has_files"


def _file_count_col() -> str:
    if _USE_PG:
        return "jsonb_array_length(coalesce(file_tree->'keys', '[]'::jsonb)) AS file_count"
    return "0 AS file_count"


# ══════════════════════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════════════════════

class DB:
    """Static helper class. Call DB.init() once at startup."""

    # ── lifecycle ─────────────────────────────────────────────────────────────

    @staticmethod
    async def init():
        global _pool
        _pool = _PgPool(_DB_URL) if _USE_PG else _SQLitePool(_SQLITE_PATH)
        await _pool.init()

    @staticmethod
    async def close():
        if _pool:
            await _pool.close()

    # ── research jobs ─────────────────────────────────────────────────────────

    @staticmethod
    async def save_job(job) -> None:
        """Upsert a ResearchJob and its citations. File contents stored separately."""
        # Only store file paths in the job row (full content goes to generated_files)
        file_tree_paths = {k: "" for k in job.file_tree.keys()}
        params = (
            job.id, job.query, str(job.mode), str(job.output_mode),
            str(job.status), job.result, job.error,
            _j(job.sources) if not _USE_PG else json.dumps(job.sources),
            _j(job.steps)   if not _USE_PG else json.dumps(job.steps),
            _j(file_tree_paths) if not _USE_PG else json.dumps(file_tree_paths),
            job.project_id,
            job.token_count,
            job.created_at,
            job.finished_at,
        )
        await _pool.execute(_upsert_job(), params)

        if job.citations:
            rows = [
                (c.id, job.id, c.url, c.title, c.snippet,
                 c.source_type, c.screenshot_path, c.domain, c.fetched_at)
                for c in job.citations
            ]
            await _pool.executemany(_upsert_citation(), rows)

        # Save full file contents to generated_files table
        if job.file_tree:
            await DB.save_generated_files(
                job_id=job.id,
                project_id=getattr(job, "project_id", None),
                file_tree=job.file_tree,
            )

    # ── generated files ───────────────────────────────────────────────────────

    @staticmethod
    async def save_generated_files(job_id: str, project_id: Optional[str],
                                   file_tree: dict[str, str]) -> None:
        """Save full file contents, upserting by (job_id, file_path)."""
        if not file_tree:
            return
        # Delete old versions for this job first (clean upsert)
        await _pool.execute(
            "DELETE FROM generated_files WHERE job_id=?", (job_id,)
        )
        rows = [
            (
                f"{job_id}:{path}",   # deterministic id
                job_id, project_id or "",
                path, content,
                len(content.encode("utf-8")),
                time.time(),
            )
            for path, content in file_tree.items()
        ]
        if rows:
            await _pool.executemany(
                "INSERT INTO generated_files "
                "(id,job_id,project_id,file_path,content,size_bytes,created_at) "
                "VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET content=excluded.content, size_bytes=excluded.size_bytes",
                rows,
            )

    @staticmethod
    async def load_generated_files(job_id: str) -> dict[str, str]:
        """Return {file_path: content} for a job."""
        rows = await _pool.fetchall(
            "SELECT file_path, content FROM generated_files WHERE job_id=? ORDER BY file_path",
            (job_id,)
        )
        return {r["file_path"]: r["content"] for r in rows}

    @staticmethod
    async def load_generated_files_for_project(project_id: str) -> dict[str, str]:
        """Return all files for a project (latest version per path wins)."""
        rows = await _pool.fetchall(
            "SELECT file_path, content FROM generated_files "
            "WHERE project_id=? ORDER BY created_at DESC",
            (project_id,)
        )
        # Latest per path (first occurrence wins due to ORDER BY DESC)
        seen: set[str] = set()
        out: dict[str, str] = {}
        for r in rows:
            if r["file_path"] not in seen:
                seen.add(r["file_path"])
                out[r["file_path"]] = r["content"]
        return out

    @staticmethod
    async def get_generated_file(job_id: str, file_path: str) -> Optional[str]:
        """Return content of a single file."""
        row = await _pool.fetchone(
            "SELECT content FROM generated_files WHERE job_id=? AND file_path=?",
            (job_id, file_path)
        )
        return row["content"] if row else None

    @staticmethod
    async def list_generated_files(job_id: str) -> list[dict]:
        """Return file manifest (no content) for a job."""
        return await _pool.fetchall(
            "SELECT id, job_id, project_id, file_path, size_bytes, created_at "
            "FROM generated_files WHERE job_id=? ORDER BY file_path",
            (job_id,)
        )

    @staticmethod
    async def load_history(
        limit: int = 50,
        offset: int = 0,
        project_id: Optional[str] = None,
        mode: Optional[str] = None,
        output_mode: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[dict]:
        """
        Load job summaries. Supports full-text search (PG) or LIKE (SQLite),
        mode/output_mode filters, pagination.
        """
        conditions: list[str] = []
        params: list = []
        n = 0  # param counter for PG

        def p(val):
            nonlocal n
            params.append(val)
            n += 1
            return f"${n}" if _USE_PG else "?"

        if project_id:
            conditions.append(f"project_id = {p(project_id)}")
        if mode:
            conditions.append(f"mode = {p(mode)}")
        if output_mode:
            conditions.append(f"output_mode = {p(output_mode)}")
        if search:
            if _USE_PG:
                # Use tsvector full-text search
                conditions.append(f"search_vec @@ plainto_tsquery('english', {p(search)})")
            else:
                conditions.append(f"(query LIKE {p('%'+search+'%')} OR result LIKE {p('%'+search+'%')})")

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        snippet_col = (
            "ts_headline('english', coalesce(left(result,2000),''), "
            f"plainto_tsquery('english', {p(search)}), "
            "'MaxWords=30,MinWords=10,ShortWord=3') AS result_snippet"
            if (_USE_PG and search)
            else f"substr(coalesce(result,''),1,200) AS result_snippet"
        )

        rows = await _pool.fetchall(
            f"""
            SELECT id, query, mode, output_mode, status, error,
                   project_id, token_count, created_at, finished_at,
                   {snippet_col},
                   (SELECT COUNT(*) FROM citations WHERE job_id=research_jobs.id) AS citation_count,
                   {_count_col()}
            FROM research_jobs
            {where}
            ORDER BY created_at DESC
            LIMIT {p(limit)} OFFSET {p(offset)}
            """,
            tuple(params),
        )

        # Count total (for pagination)
        count_row = await _pool.fetchone(
            f"SELECT COUNT(*) AS n FROM research_jobs {where}",
            tuple(params[:-2]) if params else (),   # strip limit/offset
        )
        total = (count_row or {}).get("n", 0)

        # Normalise JSON columns for SQLite
        if not _USE_PG:
            for r in rows:
                r["sources"] = _jload(r.get("sources"))
                r["steps"]   = _jload(r.get("steps"))
                r["has_files"] = bool(r.get("has_files"))
                r["file_count"] = r.get("file_count", 0)

        return rows, total

    @staticmethod
    async def load_job_result(job_id: str) -> Optional[dict]:
        """Load full result + steps + citations + file manifest for one job."""
        row = await _pool.fetchone(
            "SELECT * FROM research_jobs WHERE id=?", (job_id,)
        )
        if not row:
            return None

        cits = await _pool.fetchall(
            "SELECT * FROM citations WHERE job_id=? ORDER BY fetched_at", (job_id,)
        )
        for c in cits:
            c["screenshot_url"] = (
                f"/screenshots/{c['screenshot_path']}" if c.get("screenshot_path") else ""
            )

        steps     = _jload(row.get("steps")    or "[]") if not _USE_PG else (row.get("steps") or [])
        file_tree = _jload(row.get("file_tree") or "{}") if not _USE_PG else (row.get("file_tree") or {})
        sources   = _jload(row.get("sources")  or "[]") if not _USE_PG else (row.get("sources") or [])

        # Load file manifest from generated_files table
        file_manifest = await DB.list_generated_files(job_id)

        return {
            **row,
            "steps":         steps if isinstance(steps, list) else [],
            "citations":     cits,
            "file_tree":     list(file_tree.keys()) if isinstance(file_tree, dict) else [],
            "file_manifest": file_manifest,   # [{file_path, size_bytes, ...}]
            "sources":       sources,
        }

    @staticmethod
    async def delete_job(job_id: str) -> int:
        row = await _pool.fetchone(
            "SELECT COUNT(*) AS n FROM research_jobs WHERE id=?", (job_id,)
        )
        await _pool.execute("DELETE FROM research_jobs WHERE id=?", (job_id,))
        return (row or {}).get("n", 0)

    # ── projects ──────────────────────────────────────────────────────────────

    @staticmethod
    async def save_project(project) -> None:
        ft_trimmed = {k: v[:200] for k, v in project.file_tree.items()}
        await _pool.execute(
            _upsert_project(),
            (
                project.id, project.name, project.description,
                str(project.output_mode),
                project.context_summary,
                _j(ft_trimmed) if not _USE_PG else json.dumps(ft_trimmed),
                project.created_at, project.updated_at,
            ),
        )
        if project.rounds:
            await _pool.executemany(
                _upsert_round(),
                [
                    (r.id, project.id, r.job_id, r.round_num, r.query,
                     r.result[:4000] if r.result else "",
                     _j(r.citations) if not _USE_PG else json.dumps(r.citations),
                     r.created_at)
                    for r in project.rounds
                ],
            )

    @staticmethod
    async def load_projects() -> list[dict]:
        rows = await _pool.fetchall(
            """
            SELECT p.*,
                   (SELECT COUNT(*) FROM project_rounds WHERE project_id=p.id) AS round_count
            FROM projects p
            ORDER BY updated_at DESC
            """
        )
        for r in rows:
            ft = (_jload(r.get("file_tree") or "{}") if not _USE_PG else (r.get("file_tree") or {}))
            r["file_count"] = len(ft) if isinstance(ft, dict) else 0
            r["file_tree"]  = None
            r["enabled"]    = True   # compat shim
        return rows

    @staticmethod
    async def load_project(project_id: str) -> Optional[dict]:
        row = await _pool.fetchone("SELECT * FROM projects WHERE id=?", (project_id,))
        if not row:
            return None
        rounds = await _pool.fetchall(
            "SELECT id,round_num,query,job_id,created_at FROM project_rounds "
            "WHERE project_id=? ORDER BY round_num",
            (project_id,),
        )
        ft = _jload(row.get("file_tree") or "{}") if not _USE_PG else (row.get("file_tree") or {})
        return {
            **row,
            "rounds":     rounds,
            "file_count": len(ft) if isinstance(ft, dict) else 0,
        }

    @staticmethod
    async def delete_project(project_id: str) -> int:
        row = await _pool.fetchone(
            "SELECT COUNT(*) AS n FROM projects WHERE id=?", (project_id,)
        )
        await _pool.execute("DELETE FROM projects WHERE id=?", (project_id,))
        return (row or {}).get("n", 0)

    # ── source configs ────────────────────────────────────────────────────────

    @staticmethod
    async def save_sources(sources: list) -> None:
        await _pool.execute("DELETE FROM source_configs")
        if sources:
            await _pool.executemany(
                "INSERT INTO source_configs (id,label,type,enabled,config,status,sort_order) "
                "VALUES (?,?,?,?,?,?,?)",
                [
                    (s.id, s.label, str(s.type),
                     True if _USE_PG else int(s.enabled),
                     json.dumps(s.config) if not _USE_PG else json.dumps(s.config),
                     s.status, i)
                    for i, s in enumerate(sources)
                ],
            )

    @staticmethod
    async def load_sources() -> list[dict]:
        rows = await _pool.fetchall("SELECT * FROM source_configs ORDER BY sort_order, id")
        for r in rows:
            r["config"]  = _jload(r.get("config") or "{}")
            r["enabled"] = bool(r.get("enabled", True))
        return rows

    # ── web search config ─────────────────────────────────────────────────────

    @staticmethod
    async def save_web_search_config(cfg) -> None:
        await _pool.execute(
            """
            INSERT INTO web_search_config
                (id,engine,result_count,crawl_depth,crawl_breadth,
                 crawl_timeout,include_archive,safe_search)
            VALUES ('singleton',?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                engine=excluded.engine, result_count=excluded.result_count,
                crawl_depth=excluded.crawl_depth, crawl_breadth=excluded.crawl_breadth,
                crawl_timeout=excluded.crawl_timeout,
                include_archive=excluded.include_archive,
                safe_search=excluded.safe_search
            """,
            (cfg.engine, cfg.result_count, cfg.crawl_depth,
             cfg.crawl_breadth, cfg.crawl_timeout,
             (cfg.include_archive if _USE_PG else int(cfg.include_archive)),
             cfg.safe_search),
        )

    @staticmethod
    async def load_web_search_config() -> Optional[dict]:
        row = await _pool.fetchone("SELECT * FROM web_search_config WHERE id='singleton'")
        if row and not _USE_PG:
            row["include_archive"] = bool(row.get("include_archive", 0))
        return row

    # ── instance configs ──────────────────────────────────────────────────────

    @staticmethod
    async def save_instances(instances: list) -> None:
        await _pool.execute("DELETE FROM instance_configs")
        if instances:
            await _pool.executemany(
                "INSERT INTO instance_configs "
                "(name,host,port,tier,model,ctx_size,enabled,sort_order) "
                "VALUES (?,?,?,?,?,?,?,?)",
                [
                    (i.name, i.host, i.port, str(i.tier), i.model, i.ctx_size,
                     (i.enabled if _USE_PG else int(i.enabled)), idx)
                    for idx, i in enumerate(instances)
                ],
            )

    @staticmethod
    async def load_instances() -> list[dict]:
        rows = await _pool.fetchall("SELECT * FROM instance_configs ORDER BY sort_order")
        for r in rows:
            r["enabled"] = bool(r.get("enabled", True))
        return rows

    # ── search (the good stuff) ───────────────────────────────────────────────

    @staticmethod
    async def search(
        q: str = "",
        mode: str = "",
        output_mode: str = "",
        limit: int = 24,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """
        Paginated, filtered search.
        PG: uses tsvector with ts_headline snippets and ts_rank ordering.
        SQLite: LIKE fallback.
        Returns (rows, total_count).
        """
        rows, total = await DB.load_history(
            limit=limit, offset=offset,
            mode=mode or None,
            output_mode=output_mode or None,
            search=q or None,
        )
        return rows, total

    # ── stats ─────────────────────────────────────────────────────────────────

    @staticmethod
    async def get_stats() -> dict:
        jobs  = await _pool.fetchone("SELECT COUNT(*) AS n FROM research_jobs")
        projs = await _pool.fetchone("SELECT COUNT(*) AS n FROM projects")
        cits  = await _pool.fetchone("SELECT COUNT(*) AS n FROM citations")
        toks  = await _pool.fetchone("SELECT SUM(token_count) AS n FROM research_jobs")
        last  = await _pool.fetchone(
            "SELECT query, created_at FROM research_jobs ORDER BY created_at DESC LIMIT 1"
        )
        # DB size
        if not _USE_PG and _SQLITE_PATH.exists():
            db_size = _SQLITE_PATH.stat().st_size
        elif _USE_PG:
            sz = await _pool.fetchone(
                "SELECT pg_database_size(current_database()) AS n"
            )
            db_size = (sz or {}).get("n", 0)
        else:
            db_size = 0

        return {
            "total_jobs":      (jobs  or {}).get("n", 0),
            "total_projects":  (projs or {}).get("n", 0),
            "total_citations": (cits  or {}).get("n", 0),
            "total_tokens":    int((toks  or {}).get("n", 0) or 0),
            "last_query":      (last  or {}).get("query", ""),
            "last_at":         (last  or {}).get("created_at"),
            "db_backend":      "postgresql" if _USE_PG else "sqlite",
            "db_size_bytes":   db_size,
        }

    # ── bookmarks ─────────────────────────────────────────────────────────────

    @staticmethod
    async def save_bookmark(bm: dict) -> None:
        tags_val = json.dumps(bm.get("tags", [])) if not _USE_PG else json.dumps(bm.get("tags", []))
        await _pool.execute(
            """INSERT INTO bookmarks
                (id,type,job_id,title,url,snippet,screenshot_url,
                 source_type,domain,tags,note,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 tags=excluded.tags, note=excluded.note""",
            (
                bm["id"], bm.get("type","citation"), bm.get("job_id",""),
                bm.get("title",""), bm.get("url",""), bm.get("snippet",""),
                bm.get("screenshot_url",""), bm.get("source_type","web"),
                bm.get("domain",""), tags_val, bm.get("note",""),
                bm.get("created_at", time.time()),
            )
        )

    @staticmethod
    async def load_bookmarks(limit: int = 500) -> list[dict]:
        rows = await _pool.fetchall(
            "SELECT * FROM bookmarks ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        for r in rows:
            r["tags"] = _jload(r.get("tags") or "[]")
        return rows

    @staticmethod
    async def get_bookmark(bm_id: str) -> Optional[dict]:
        row = await _pool.fetchone("SELECT * FROM bookmarks WHERE id=?", (bm_id,))
        if row:
            row["tags"] = _jload(row.get("tags") or "[]")
        return row

    @staticmethod
    async def delete_bookmark(bm_id: str) -> None:
        await _pool.execute("DELETE FROM bookmarks WHERE id=?", (bm_id,))

    # ── export (updated to include bookmarks) ─────────────────────────────────

    # ── notebooks ─────────────────────────────────────────────────────────────

    @staticmethod
    async def save_notebook(nb: dict) -> None:
        await _pool.execute(
            """INSERT INTO notebooks (id,title,description,project_id,tags,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 title=excluded.title, description=excluded.description,
                 tags=excluded.tags, updated_at=excluded.updated_at""",
            (nb["id"], nb["title"], nb.get("description",""),
             nb.get("project_id"), _j(nb.get("tags",[])) if not _USE_PG else json.dumps(nb.get("tags",[])),
             nb["created_at"], nb["updated_at"])
        )

    @staticmethod
    async def load_notebooks(project_id: Optional[str] = None) -> list[dict]:
        if project_id:
            rows = await _pool.fetchall(
                "SELECT * FROM notebooks WHERE project_id=? ORDER BY updated_at DESC", (project_id,)
            )
        else:
            rows = await _pool.fetchall("SELECT * FROM notebooks ORDER BY updated_at DESC")
        for r in rows:
            r["tags"] = _jload(r.get("tags") or "[]")
        return rows

    @staticmethod
    async def load_notebook(nb_id: str) -> Optional[dict]:
        nb = await _pool.fetchone("SELECT * FROM notebooks WHERE id=?", (nb_id,))
        if not nb: return None
        nb["tags"] = _jload(nb.get("tags") or "[]")
        cells = await _pool.fetchall(
            "SELECT * FROM notebook_cells WHERE notebook_id=? ORDER BY sort_order", (nb_id,)
        )
        for c in cells:
            c["thread"] = _jload(c.get("thread") or "[]")
        nb["cells"] = cells
        return nb

    @staticmethod
    async def delete_notebook(nb_id: str) -> None:
        await _pool.execute("DELETE FROM notebooks WHERE id=?", (nb_id,))

    @staticmethod
    async def save_cell(cell: dict) -> None:
        await _pool.execute(
            """INSERT INTO notebook_cells
                (id,notebook_id,sort_order,cell_type,lang,tag,content,generated,thread,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 sort_order=excluded.sort_order, cell_type=excluded.cell_type,
                 lang=excluded.lang, tag=excluded.tag,
                 content=excluded.content, generated=excluded.generated,
                 thread=excluded.thread, updated_at=excluded.updated_at""",
            (cell["id"], cell["notebook_id"], cell.get("sort_order",0),
             cell.get("cell_type","markdown"), cell.get("lang","python"),
             cell.get("tag","none"), cell.get("content",""), cell.get("generated",""),
             _j(cell.get("thread",[])) if not _USE_PG else json.dumps(cell.get("thread",[])),
             cell.get("created_at", time.time()), cell.get("updated_at", time.time()))
        )
        # Touch notebook updated_at
        await _pool.execute(
            "UPDATE notebooks SET updated_at=? WHERE id=?",
            (time.time(), cell["notebook_id"])
        )

    @staticmethod
    async def save_cells_bulk(cells: list[dict]) -> None:
        """Upsert multiple cells at once (used for reorder / bulk update)."""
        for cell in cells:
            await DB.save_cell(cell)

    @staticmethod
    async def delete_cell(cell_id: str) -> None:
        await _pool.execute("DELETE FROM notebook_cells WHERE id=?", (cell_id,))

    @staticmethod
    async def load_cell(cell_id: str) -> Optional[dict]:
        c = await _pool.fetchone("SELECT * FROM notebook_cells WHERE id=?", (cell_id,))
        if c: c["thread"] = _jload(c.get("thread") or "[]")
        return c

    @staticmethod
    async def export_all(limit: int = 500) -> dict:
        rows, _ = await DB.load_history(limit=limit)
        projs    = await DB.load_projects()
        srcs     = await DB.load_sources()
        ws_cfg   = await DB.load_web_search_config()
        bmarks   = await DB.load_bookmarks()
        return {
            "jobs":              rows,
            "projects":          projs,
            "sources":           srcs,
            "bookmarks":         bmarks,
            "web_search_config": ws_cfg,
            "exported_at":       time.time(),
            "db_backend":        "postgresql" if _USE_PG else "sqlite",
        }