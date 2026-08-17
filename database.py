import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from config import BASE_DIR, database_settings, uses_postgres

DB_PATH = os.environ.get("SCRAPER_DB", os.path.join(BASE_DIR, "scraper.db"))

_context = {
    "run_id": None,
    "handle": None,
    "db_path": None,
}


def _pk(backend: str) -> str:
    if backend == "postgres":
        return "SERIAL PRIMARY KEY"
    return "INTEGER PRIMARY KEY AUTOINCREMENT"


def schema_statements(backend: str) -> list[str]:
    pk = _pk(backend)
    return [
        """
        CREATE TABLE IF NOT EXISTS channels (
            handle TEXT PRIMARY KEY,
            start_date TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS scrape_runs (
            id {pk},
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            error TEXT
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS users (
            id {pk},
            handle TEXT,
            instagram_id TEXT,
            raw_json TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            scrape_run_id INTEGER,
            FOREIGN KEY (scrape_run_id) REFERENCES scrape_runs(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY,
            handle TEXT NOT NULL,
            taken_at INTEGER,
            caption TEXT,
            raw_json TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            scrape_run_id INTEGER,
            FOREIGN KEY (scrape_run_id) REFERENCES scrape_runs(id)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS media (
            id {pk},
            post_id TEXT NOT NULL,
            media_type TEXT NOT NULL,
            url TEXT NOT NULL,
            local_path TEXT,
            downloaded INTEGER NOT NULL DEFAULT 0,
            UNIQUE(post_id, url),
            FOREIGN KEY (post_id) REFERENCES posts(id)
        )
        """,
    ]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _backend_for(db_path: Optional[str] = None) -> str:
    path = db_path or _context.get("db_path")
    return "postgres" if uses_postgres(path) else "sqlite"


def describe_database(db_path: Optional[str] = None) -> str:
    if _backend_for(db_path) != "postgres":
        return db_path or _context.get("db_path") or DB_PATH
    settings = database_settings()
    return (
        f"PostgreSQL database '{settings['name']}' on "
        f"{settings['host']}:{settings['port']} (user {settings['user']})"
    )


def _connect_postgres(dbname: str):
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL support needs the psycopg2 package. Run: pip install -r requirements.txt"
        ) from exc

    settings = database_settings()
    conn = psycopg2.connect(
        host=settings["host"],
        port=settings["port"],
        dbname=dbname,
        user=settings["user"],
        password=settings["password"] or None,
    )
    conn.cursor_factory = RealDictCursor
    return conn


def create_project_database() -> str:
    """Create the dedicated insta_scraper database if it does not exist yet."""
    from psycopg2 import sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    settings = database_settings()
    name = settings["name"]
    admin_db = os.environ.get("POSTGRES_ADMIN_DB", "postgres")
    try:
        conn = _connect_postgres(admin_db)
    except Exception as exc:
        raise RuntimeError(
            f"Could not connect to PostgreSQL at {settings['host']}:{settings['port']} "
            f"as user '{settings['user']}'. Make sure PostgreSQL is running, then put your "
            f"Postgres username and password in the [database] section of dhs622_config.cfg.\n"
            f"Details: {exc}"
        ) from exc

    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
            exists = cur.fetchone() is not None
            if not exists:
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    finally:
        conn.close()
    return name


def _apply_schema(conn, backend: str) -> None:
    for statement in schema_statements(backend):
        _execute(conn, backend, statement)


def _execute(conn, backend: str, sql: str, params=()):
    if backend == "postgres":
        sql = sql.replace("?", "%s")
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur
    return conn.execute(sql, params)


@contextmanager
def get_connection(db_path: Optional[str] = None):
    backend = _backend_for(db_path)
    if backend == "postgres":
        conn = _connect_postgres(database_settings()["name"])
        try:
            yield conn, backend
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return

    path = db_path or _context.get("db_path") or DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn, backend
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None) -> str:
    if _backend_for(db_path) == "postgres":
        create_project_database()
        with get_connection(db_path) as (conn, backend):
            _apply_schema(conn, backend)
        return describe_database(db_path)

    path = db_path or DB_PATH
    with get_connection(path) as (conn, backend):
        _apply_schema(conn, backend)
    return path


def set_scrape_context(run_id: Optional[int], handle: Optional[str], db_path: Optional[str] = None) -> None:
    _context["run_id"] = run_id
    _context["handle"] = handle
    _context["db_path"] = db_path


def start_run(db_path: Optional[str] = None) -> int:
    with get_connection(db_path) as (conn, backend):
        sql = "INSERT INTO scrape_runs (started_at, status) VALUES (?, ?)"
        if backend == "postgres":
            sql += " RETURNING id"
        cursor = _execute(conn, backend, sql, (_now(), "running"))
        if backend == "postgres":
            return int(cursor.fetchone()["id"])
        return int(cursor.lastrowid)


def finish_run(run_id: int, status: str, error: Optional[str] = None, db_path: Optional[str] = None) -> None:
    with get_connection(db_path) as (conn, backend):
        _execute(
            conn,
            backend,
            "UPDATE scrape_runs SET finished_at = ?, status = ?, error = ? WHERE id = ?",
            (_now(), status, error, run_id),
        )


def upsert_channel(handle: str, start_date: Optional[str] = None, db_path: Optional[str] = None) -> None:
    with get_connection(db_path) as (conn, backend):
        _execute(
            conn,
            backend,
            """
            INSERT INTO channels (handle, start_date, enabled, created_at)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(handle) DO UPDATE SET
                start_date = COALESCE(excluded.start_date, channels.start_date),
                enabled = 1
            """,
            (handle, start_date, _now()),
        )


def list_channels(db_path: Optional[str] = None) -> list[str]:
    with get_connection(db_path) as (conn, backend):
        rows = _execute(
            conn,
            backend,
            "SELECT handle FROM channels WHERE enabled = 1 ORDER BY handle",
        ).fetchall()
    return [row["handle"] for row in rows]


def _caption_from_post(post: dict) -> Optional[str]:
    caption = post.get("caption")
    if isinstance(caption, dict):
        text = caption.get("text")
        return text if isinstance(text, str) else None
    if isinstance(caption, str):
        return caption
    return None


def save_user(user_record: dict, handle: Optional[str] = None, db_path: Optional[str] = None) -> None:
    active_handle = handle or _context.get("handle") or user_record.get("username")
    with get_connection(db_path) as (conn, backend):
        _execute(
            conn,
            backend,
            """
            INSERT INTO users (handle, instagram_id, raw_json, captured_at, scrape_run_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                active_handle,
                str(user_record.get("id") or user_record.get("pk") or ""),
                json.dumps(user_record),
                _now(),
                _context.get("run_id"),
            ),
        )


def save_posts(posts: list[dict], handle: Optional[str] = None, db_path: Optional[str] = None) -> int:
    active_handle = handle or _context.get("handle")
    saved = 0
    with get_connection(db_path) as (conn, backend):
        for post in posts:
            post_id = post.get("id") or post.get("pk")
            if not post_id:
                continue
            taken_at = post.get("taken_at") or post.get("taken_at_timestamp") or post.get("created_at")
            if not isinstance(taken_at, (int, float)):
                taken_at = None
            _execute(
                conn,
                backend,
                """
                INSERT INTO posts (id, handle, taken_at, caption, raw_json, captured_at, scrape_run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    handle = excluded.handle,
                    taken_at = excluded.taken_at,
                    caption = excluded.caption,
                    raw_json = excluded.raw_json,
                    captured_at = excluded.captured_at,
                    scrape_run_id = excluded.scrape_run_id
                """,
                (
                    str(post_id),
                    active_handle or "",
                    int(taken_at) if taken_at is not None else None,
                    _caption_from_post(post),
                    json.dumps(post),
                    _now(),
                    _context.get("run_id"),
                ),
            )
            saved += 1
    return saved


def list_posts(handle: Optional[str] = None, db_path: Optional[str] = None) -> list[dict]:
    query = "SELECT id, handle, taken_at, caption, raw_json FROM posts"
    params: list = []
    if handle:
        query += " WHERE handle = ?"
        params.append(handle)
    query += " ORDER BY taken_at DESC"
    with get_connection(db_path) as (conn, backend):
        rows = _execute(conn, backend, query, params).fetchall()
    return [dict(row) for row in rows]


def upsert_media(post_id: str, media_type: str, url: str, db_path: Optional[str] = None) -> None:
    with get_connection(db_path) as (conn, backend):
        _execute(
            conn,
            backend,
            """
            INSERT INTO media (post_id, media_type, url, downloaded)
            VALUES (?, ?, ?, 0)
            ON CONFLICT(post_id, url) DO NOTHING
            """,
            (str(post_id), media_type, url),
        )


def mark_media_downloaded(url: str, local_path: str, db_path: Optional[str] = None) -> None:
    with get_connection(db_path) as (conn, backend):
        _execute(
            conn,
            backend,
            "UPDATE media SET downloaded = 1, local_path = ? WHERE url = ?",
            (local_path, url),
        )


def status_summary(db_path: Optional[str] = None) -> dict:
    with get_connection(db_path) as (conn, backend):
        channels = _execute(
            conn, backend, "SELECT COUNT(*) AS n FROM channels WHERE enabled = 1"
        ).fetchone()["n"]
        posts = _execute(conn, backend, "SELECT COUNT(*) AS n FROM posts").fetchone()["n"]
        media = _execute(conn, backend, "SELECT COUNT(*) AS n FROM media").fetchone()["n"]
        downloaded = _execute(
            conn, backend, "SELECT COUNT(*) AS n FROM media WHERE downloaded = 1"
        ).fetchone()["n"]
        last_run = _execute(
            conn,
            backend,
            "SELECT id, started_at, finished_at, status, error FROM scrape_runs ORDER BY id DESC LIMIT 1",
        ).fetchone()
    return {
        "channels": channels,
        "posts": posts,
        "media": media,
        "downloaded": downloaded,
        "last_run": dict(last_run) if last_run else None,
    }
