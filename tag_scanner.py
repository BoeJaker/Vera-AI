import os
import re
import json
import hashlib
import sqlite3
import subprocess
import threading
import time
from datetime import datetime
from typing import List, Dict, Optional

try:
    import redis
except ImportError:
    redis = None

try:
    import psycopg2
except ImportError:
    psycopg2 = None

try:
    import requests
except ImportError:
    requests = None

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    Observer = None


# ---------------- CONFIG ----------------

class TodoCollectorConfig:
    def __init__(
        self,
        todo_filenames=None,
        todo_tags=None,
        datastore_path=".todo_index.db",
        ignore_file=".todoignore",
        use_git_diff=True,
        include_git_metadata=True,
        redis_url=None,
        postgres_dsn=None,
        git_provider=None,  # "github" or "gitlab"
        git_token=None,
    ):
        self.todo_filenames = todo_filenames or ["TODO.md"]
        self.todo_tags = todo_tags or ["TODO", "FIXME", "HACK"]
        self.datastore_path = datastore_path
        self.ignore_file = ignore_file
        self.use_git_diff = use_git_diff
        self.include_git_metadata = include_git_metadata
        self.redis_url = redis_url
        self.postgres_dsn = postgres_dsn
        self.git_provider = git_provider
        self.git_token = git_token


# ---------------- WATCHER ----------------

class TodoWatcher(FileSystemEventHandler):
    def __init__(self, collector):
        self.collector = collector

    def on_modified(self, event):
        if not event.is_directory:
            self.collector.process_file(event.src_path)


# ---------------- CORE ----------------

class TodoCollector:
    def __init__(self, root_dir: str, config: TodoCollectorConfig = None):
        self.root_dir = os.path.abspath(root_dir)
        self.config = config or TodoCollectorConfig()

        self.ignore_patterns = self._load_ignore()
        self.redis = redis.from_url(self.config.redis_url) if (self.config.redis_url and redis) else None
        self.pg_conn = psycopg2.connect(self.config.postgres_dsn) if (self.config.postgres_dsn and psycopg2) else None

        self.sqlite_conn = sqlite3.connect(os.path.join(self.root_dir, self.config.datastore_path))
        self._init_sqlite()

    # ---------------- IGNORE ----------------

    def _load_ignore(self):
        path = os.path.join(self.root_dir, self.config.ignore_file)
        if not os.path.exists(path):
            return []
        return [l.strip() for l in open(path) if l.strip() and not l.startswith("#")]

    def _is_ignored(self, path):
        rel = os.path.relpath(path, self.root_dir)
        return any(re.match(p.replace("*", ".*"), rel) for p in self.ignore_patterns)

    # ---------------- MAIN ----------------

    def collect(self):
        files = self._get_target_files()
        for f in files:
            self.process_file(f)

        self._import_git_issues()

    def process_file(self, path):
        if self._is_ignored(path):
            return

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f, 1):
                    entry = self._parse_line(path, i, line)
                    if entry:
                        self._store(entry)
        except Exception:
            pass

    # ---------------- FILE SELECTION ----------------

    def _get_target_files(self):
        if self.config.use_git_diff:
            try:
                out = subprocess.check_output(["git", "diff", "--name-only"], cwd=self.root_dir)
                return [os.path.join(self.root_dir, f) for f in out.decode().splitlines()]
            except Exception:
                pass

        files = []
        for root, _, names in os.walk(self.root_dir):
            for n in names:
                files.append(os.path.join(root, n))
        return files

    # ---------------- PARSING ----------------

    def _parse_line(self, path, line_no, line):
        tag_pattern = r"(" + "|".join(self.config.todo_tags) + r")\((.*?)\)?:\s*(.*)"
        m = re.search(tag_pattern, line)
        if not m:
            return None

        tag, meta, content = m.groups()
        metadata = self._parse_metadata(meta)
        return self._build_entry(path, line_no, content, tag, metadata)

    def _parse_metadata(self, meta):
        result = {}
        if not meta:
            return result
        for pair in meta.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                result[k.strip()] = v.strip()
        return result

    # ---------------- ENTRY ----------------

    def _build_entry(self, path, line, content, tag, metadata):
        rel = os.path.relpath(path, self.root_dir)
        eid = hashlib.sha1(f"{rel}:{line}:{content}".encode()).hexdigest()

        entry = {
            "id": eid,
            "file": rel,
            "line": line,
            "tag": tag,
            "content": content.strip(),
            "metadata": metadata,
            "status": "open",
            "history": [],
            "updated_at": datetime.utcnow().isoformat(),
        }

        if self.config.include_git_metadata:
            entry.update(self._git_meta(path, line))

        return entry

    def _git_meta(self, path, line):
        try:
            out = subprocess.check_output([
                "git", "blame", "-L", f"{line},{line}", "--line-porcelain", path
            ], cwd=self.root_dir).decode()

            data = {}
            for l in out.splitlines():
                if l.startswith("author "):
                    data["git_author"] = l[7:]
                elif l.startswith("author-time "):
                    ts = int(l.split()[1])
                    data["git_timestamp"] = datetime.utcfromtimestamp(ts).isoformat()
                elif "git_commit" not in data:
                    data["git_commit"] = l.split()[0]
            return data
        except:
            return {}

    # ---------------- STORAGE ----------------

    def _init_sqlite(self):
        cur = self.sqlite_conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id TEXT PRIMARY KEY,
            file TEXT,
            line INT,
            tag TEXT,
            content TEXT,
            metadata TEXT,
            status TEXT,
            history TEXT,
            updated_at TEXT
        )
        """)
        self.sqlite_conn.commit()

    def _store(self, entry):
        cur = self.sqlite_conn.cursor()
        cur.execute("SELECT status, history FROM todos WHERE id=?", (entry["id"],))
        row = cur.fetchone()

        if row:
            entry["status"] = row[0]
            entry["history"] = json.loads(row[1]) if row[1] else []
        else:
            entry["history"] = [{"event": "created", "ts": datetime.utcnow().isoformat()}]

        cur.execute("""
        INSERT OR REPLACE INTO todos VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            entry["id"], entry["file"], entry["line"], entry["tag"],
            entry["content"], json.dumps(entry["metadata"]),
            entry["status"], json.dumps(entry["history"]), entry["updated_at"]
        ))
        self.sqlite_conn.commit()

        self._emit(entry)
        self._replicate(entry)

    # ---------------- EVENTS ----------------

    def _emit(self, entry):
        if self.redis:
            self.redis.xadd("todo.events", {
                "type": "todo.detected",
                "payload": json.dumps(entry)
            })

    # ---------------- REPLICATION ----------------

    def _replicate(self, entry):
        if not self.pg_conn:
            return
        cur = self.pg_conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id TEXT PRIMARY KEY,
            file TEXT,
            line INT,
            tag TEXT,
            content TEXT,
            metadata JSONB,
            status TEXT,
            history JSONB,
            updated_at TEXT
        )
        """)
        cur.execute("""
        INSERT INTO todos VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (id) DO UPDATE SET
            content=EXCLUDED.content,
            metadata=EXCLUDED.metadata,
            status=EXCLUDED.status,
            history=EXCLUDED.history,
            updated_at=EXCLUDED.updated_at
        """, (
            entry["id"], entry["file"], entry["line"], entry["tag"],
            entry["content"], json.dumps(entry["metadata"]),
            entry["status"], json.dumps(entry["history"]), entry["updated_at"]
        ))
        self.pg_conn.commit()

    # ---------------- GIT ISSUES ----------------

    def _import_git_issues(self):
        if not self.config.git_provider or not requests:
            return

        repo = self._get_repo_info()
        if not repo:
            return

        if self.config.git_provider == "github":
            url = f"https://api.github.com/repos/{repo}/issues"
            headers = {"Authorization": f"token {self.config.git_token}"} if self.config.git_token else {}

            issues = requests.get(url, headers=headers).json()

            for issue in issues:
                entry = {
                    "id": f"issue-{issue['id']}",
                    "file": "__external__",
                    "line": 0,
                    "tag": "ISSUE",
                    "content": issue["title"],
                    "metadata": {"url": issue["html_url"], "state": issue["state"]},
                    "status": "open" if issue["state"] == "open" else "closed",
                    "history": [],
                    "updated_at": datetime.utcnow().isoformat(),
                }
                self._store(entry)

    def _get_repo_info(self):
        try:
            url = subprocess.check_output(["git", "config", "--get", "remote.origin.url"], cwd=self.root_dir).decode().strip()
            if "github.com" in url:
                return url.split("github.com/")[1].replace(".git", "")
        except:
            return None


# ---------------- CLI ----------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--redis")
    parser.add_argument("--pg")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--git-provider")
    parser.add_argument("--git-token")

    args = parser.parse_args()

    cfg = TodoCollectorConfig(
        redis_url=args.redis,
        postgres_dsn=args.pg,
        git_provider=args.git_provider,
        git_token=args.git_token
    )

    collector = TodoCollector(args.path, cfg)
    collector.collect()

    if args.watch and Observer:
        observer = Observer()
        observer.schedule(TodoWatcher(collector), path=args.path, recursive=True)
        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
