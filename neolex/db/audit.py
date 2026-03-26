"""Append-only SQLite audit log with WAL mode.

AuditDB is the single interface for all database operations.
It is accessed through the get_audit_db() async context manager.

APPEND-ONLY CONTRACT: AuditDB exposes NO update or delete methods for
the queries or events tables. The api_keys table allows revoke (active=0)
and last_used updates but never hard-deletes rows.
"""
import datetime
import json
from contextlib import asynccontextmanager

import aiosqlite

from neolex.config import settings

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS reindex_jobs (
    job_id       TEXT PRIMARY KEY,
    client_slug  TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    progress     REAL NOT NULL DEFAULT 0.0,
    started_at   TEXT NOT NULL,
    completed_at TEXT,
    error        TEXT,
    doc_count    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS documents (
    doc_id      TEXT PRIMARY KEY,
    client_slug TEXT NOT NULL,
    filename    TEXT NOT NULL,
    size_bytes  INTEGER NOT NULL,
    upload_ts   TEXT NOT NULL,
    indexed     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS api_keys (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    key_hash    TEXT NOT NULL UNIQUE,
    key_prefix  TEXT NOT NULL,
    client_slug TEXT NOT NULL,
    scope       TEXT NOT NULL DEFAULT 'query',
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    last_used   TEXT
);

CREATE TABLE IF NOT EXISTS queries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    key_hash     TEXT NOT NULL,
    question     TEXT NOT NULL,
    answer_text  TEXT NOT NULL,
    sources_json TEXT NOT NULL,
    latency_ms   INTEGER NOT NULL,
    model_name   TEXT NOT NULL,
    ip           TEXT,
    user_agent   TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    key_hash    TEXT,
    event_type  TEXT NOT NULL,
    detail_json TEXT NOT NULL,
    ip          TEXT,
    user_agent  TEXT
);
"""


# ---------------------------------------------------------------------------
# AuditDB
# ---------------------------------------------------------------------------

class AuditDB:
    """Wrapper around an open aiosqlite connection.

    Never instantiate directly — use get_audit_db() context manager.
    """

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self._conn = conn

    # --- Schema ---

    async def init_schema(self) -> None:
        """Create tables if they do not exist. Idempotent."""
        await self._conn.executescript(_SCHEMA_SQL)
        await self._conn.commit()

    # --- Key management ---

    async def create_key(
        self,
        *,
        name: str,
        key_hash: str,
        key_prefix: str,
        client_slug: str,
        scope: str = "query",
    ) -> int:
        """Insert a new API key row. Returns the new row id."""
        ts = datetime.datetime.utcnow().isoformat()
        cur = await self._conn.execute(
            "INSERT INTO api_keys (name, key_hash, key_prefix, client_slug, scope, active, created_at) "
            "VALUES (?, ?, ?, ?, ?, 1, ?)",
            (name, key_hash, key_prefix, client_slug, scope, ts),
        )
        return cur.lastrowid  # type: ignore[return-value]

    async def get_key_by_hash(self, key_hash: str) -> aiosqlite.Row | None:
        """Return the api_keys row matching key_hash, or None."""
        async with self._conn.execute(
            "SELECT * FROM api_keys WHERE key_hash = ?", (key_hash,)
        ) as cur:
            return await cur.fetchone()

    async def list_keys(self) -> list[aiosqlite.Row]:
        """Return all rows from api_keys."""
        async with self._conn.execute("SELECT * FROM api_keys ORDER BY id") as cur:
            return await cur.fetchall()

    async def revoke_key(self, prefix: str) -> int:
        """Mark key(s) with matching key_prefix as inactive. Returns affected rows."""
        cur = await self._conn.execute(
            "UPDATE api_keys SET active = 0 WHERE key_prefix = ? AND active = 1", (prefix,)
        )
        return cur.rowcount  # type: ignore[return-value]

    async def update_last_used(self, key_id: int) -> None:
        """Update last_used timestamp for a key row. Called on every successful auth."""
        await self._conn.execute(
            "UPDATE api_keys SET last_used = ? WHERE id = ?",
            (datetime.datetime.utcnow().isoformat(), key_id),
        )

    # --- Audit log writes (append-only) ---

    async def log_query(
        self,
        *,
        key_hash: str,
        question: str,
        answer_text: str,
        sources_json: str,
        latency_ms: int,
        model_name: str,
        ip: str | None,
        user_agent: str | None,
    ) -> None:
        """Append a query log entry. No update or delete counterpart exists."""
        await self._conn.execute(
            "INSERT INTO queries "
            "(ts, key_hash, question, answer_text, sources_json, latency_ms, model_name, ip, user_agent) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.datetime.utcnow().isoformat(),
                key_hash,
                question,
                answer_text,
                sources_json,
                latency_ms,
                model_name,
                ip,
                user_agent,
            ),
        )

    async def log_event(
        self,
        *,
        key_hash: str | None,
        event_type: str,
        detail: dict,
        ip: str | None,
        user_agent: str | None,
    ) -> None:
        """Append a generic event log entry (auth failures, uploads, etc.).

        key_hash may be None for unauthenticated failures where no key was provided.
        event_type: 'auth_failure' | 'upload' | 'delete' | 'reindex' | ...
        """
        await self._conn.execute(
            "INSERT INTO events (ts, key_hash, event_type, detail_json, ip, user_agent) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                datetime.datetime.utcnow().isoformat(),
                key_hash,
                event_type,
                json.dumps(detail),
                ip,
                user_agent,
            ),
        )

    # --- Reindex job management ---

    async def create_reindex_job(
        self,
        *,
        job_id: str,
        client_slug: str,
        started_at: str,
    ) -> None:
        """Insert a new reindex job row with status='pending'."""
        await self._conn.execute(
            "INSERT INTO reindex_jobs (job_id, client_slug, status, progress, started_at) "
            "VALUES (?, ?, 'pending', 0.0, ?)",
            (job_id, client_slug, started_at),
        )

    async def get_reindex_job(self, job_id: str) -> aiosqlite.Row | None:
        """Return reindex_jobs row or None."""
        async with self._conn.execute(
            "SELECT * FROM reindex_jobs WHERE job_id = ?", (job_id,)
        ) as cur:
            return await cur.fetchone()

    async def update_reindex_job(
        self,
        job_id: str,
        *,
        status: str,
        progress: float = 0.0,
        completed_at: str | None = None,
        error: str | None = None,
        doc_count: int = 0,
    ) -> None:
        """Update status, progress, and completion fields for a job."""
        await self._conn.execute(
            "UPDATE reindex_jobs SET status=?, progress=?, completed_at=?, error=?, doc_count=? "
            "WHERE job_id=?",
            (status, progress, completed_at, error, doc_count, job_id),
        )

    # --- Document registry ---

    async def register_document(
        self,
        *,
        doc_id: str,
        client_slug: str,
        filename: str,
        size_bytes: int,
        upload_ts: str,
    ) -> None:
        """Insert a document row into the registry (idempotent on conflict)."""
        await self._conn.execute(
            "INSERT OR IGNORE INTO documents (doc_id, client_slug, filename, size_bytes, upload_ts, indexed) "
            "VALUES (?, ?, ?, ?, ?, 0)",
            (doc_id, client_slug, filename, size_bytes, upload_ts),
        )

    async def get_document(self, doc_id: str, client_slug: str) -> aiosqlite.Row | None:
        """Return documents row for a specific client's document."""
        async with self._conn.execute(
            "SELECT * FROM documents WHERE doc_id=? AND client_slug=?", (doc_id, client_slug)
        ) as cur:
            return await cur.fetchone()

    async def list_documents(self, client_slug: str) -> list[aiosqlite.Row]:
        """Return all documents for a client, newest first."""
        async with self._conn.execute(
            "SELECT * FROM documents WHERE client_slug=? ORDER BY upload_ts DESC", (client_slug,)
        ) as cur:
            return await cur.fetchall()

    async def mark_document_indexed(self, doc_id: str, client_slug: str) -> None:
        """Set indexed=1 for a document."""
        await self._conn.execute(
            "UPDATE documents SET indexed=1 WHERE doc_id=? AND client_slug=?",
            (doc_id, client_slug),
        )

    async def delete_document(self, doc_id: str, client_slug: str) -> int:
        """Delete a document row. Returns number of rows deleted."""
        cur = await self._conn.execute(
            "DELETE FROM documents WHERE doc_id=? AND client_slug=?",
            (doc_id, client_slug),
        )
        return cur.rowcount  # type: ignore[return-value]

    # --- Audit log reads (admin use) ---

    async def get_queries(self, limit: int = 50, offset: int = 0) -> list[aiosqlite.Row]:
        """Return paginated query log entries, newest first."""
        async with self._conn.execute(
            "SELECT * FROM queries ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
        ) as cur:
            return await cur.fetchall()

    async def get_events(self, limit: int = 50, offset: int = 0) -> list[aiosqlite.Row]:
        """Return paginated event log entries, newest first."""
        async with self._conn.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
        ) as cur:
            return await cur.fetchall()


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------

@asynccontextmanager
async def get_audit_db(db_path: str | None = None):
    """Async context manager that yields an AuditDB instance.

    Opens a fresh aiosqlite connection with WAL mode enabled.
    Commits on clean exit, rolls back on exception.
    Closes connection in all cases.

    Usage:
        async with get_audit_db() as db:
            row = await db.get_key_by_hash(h)
    """
    path = db_path or settings.db_path
    conn = await aiosqlite.connect(path)
    try:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = aiosqlite.Row
        db = AuditDB(conn)
        yield db
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    finally:
        await conn.close()
