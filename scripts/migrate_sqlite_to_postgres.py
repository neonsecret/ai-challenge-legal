"""
Migrate all data from SQLite (neolex.db) to PostgreSQL.

Usage:
    uv run python scripts/migrate_sqlite_to_postgres.py
"""

import asyncio
import os
import sqlite3
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")
SQLITE_PATH = os.getenv("NEOLEX_DB_PATH", str(PROJECT_ROOT / "neolex.db"))


def get_sqlite_rows(conn: sqlite3.Connection, table: str) -> list[tuple]:
    try:
        cur = conn.execute(f"SELECT * FROM {table}")
        return cur.fetchall()
    except sqlite3.OperationalError:
        return []


async def reset_sequence(pg: asyncpg.Connection, table: str, column: str = "id") -> None:
    await pg.execute(
        f"SELECT setval(pg_get_serial_sequence('{table}', '{column}'), "
        f"COALESCE((SELECT MAX({column}) FROM {table}), 1))"
    )


async def migrate() -> None:
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL is not set in .env", file=sys.stderr)
        sys.exit(1)

    sqlite_path = Path(SQLITE_PATH)
    if not sqlite_path.exists():
        print(f"SQLite database not found at {sqlite_path}. Nothing to migrate.")
        return

    # asyncpg expects postgresql:// not postgresql+asyncpg://
    pg_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgres+asyncpg://", "postgresql://"
    )

    print(f"Connecting to SQLite: {sqlite_path}")
    sqlite_conn = sqlite3.connect(str(sqlite_path))

    print("Connecting to PostgreSQL...")
    pg = await asyncpg.connect(pg_url)

    try:
        totals: dict[str, int] = {}

        # ── api_keys ──────────────────────────────────────────────────────────
        rows = get_sqlite_rows(sqlite_conn, "api_keys")
        count = 0
        for row in rows:
            id_, name, key_hash, key_prefix, client_slug, scope, active, created_at, last_used = row
            await pg.execute(
                """
                INSERT INTO api_keys (id, name, key_hash, key_prefix, client_slug, scope, active, created_at, last_used)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT DO NOTHING
                """,
                id_,
                name,
                key_hash,
                key_prefix,
                client_slug,
                scope,
                bool(active),
                created_at,
                last_used,
            )
            count += 1
        totals["api_keys"] = count
        if count:
            await reset_sequence(pg, "api_keys", "id")

        # ── queries ───────────────────────────────────────────────────────────
        rows = get_sqlite_rows(sqlite_conn, "queries")
        count = 0
        for row in rows:
            id_, ts, key_hash, question, answer_text, sources_json, latency_ms, model_name, ip, user_agent = row
            await pg.execute(
                """
                INSERT INTO queries (id, ts, key_hash, question, answer_text, sources_json, latency_ms, model_name, ip, user_agent)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT DO NOTHING
                """,
                id_,
                ts,
                key_hash,
                question,
                answer_text,
                sources_json,
                latency_ms,
                model_name,
                ip,
                user_agent,
            )
            count += 1
        totals["queries"] = count
        if count:
            await reset_sequence(pg, "queries", "id")

        # ── events ────────────────────────────────────────────────────────────
        rows = get_sqlite_rows(sqlite_conn, "events")
        count = 0
        for row in rows:
            id_, ts, key_hash, event_type, detail_json, ip, user_agent = row
            await pg.execute(
                """
                INSERT INTO events (id, ts, key_hash, event_type, detail_json, ip, user_agent)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT DO NOTHING
                """,
                id_,
                ts,
                key_hash,
                event_type,
                detail_json,
                ip,
                user_agent,
            )
            count += 1
        totals["events"] = count
        if count:
            await reset_sequence(pg, "events", "id")

        # ── rate_limits ───────────────────────────────────────────────────────
        rows = get_sqlite_rows(sqlite_conn, "rate_limits")
        count = 0
        for row in rows:
            bucket, window_start, request_count = row
            await pg.execute(
                """
                INSERT INTO rate_limits (bucket, window_start, request_count)
                VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING
                """,
                bucket,
                window_start,
                request_count,
            )
            count += 1
        totals["rate_limits"] = count

        # ── documents ─────────────────────────────────────────────────────────
        rows = get_sqlite_rows(sqlite_conn, "documents")
        count = 0
        for row in rows:
            doc_id, client_slug, filename, size_bytes, upload_ts, indexed = row
            await pg.execute(
                """
                INSERT INTO documents (doc_id, client_slug, filename, size_bytes, upload_ts, indexed)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT DO NOTHING
                """,
                doc_id,
                client_slug,
                filename,
                size_bytes,
                upload_ts,
                bool(indexed),
            )
            count += 1
        totals["documents"] = count

        # ── reindex_jobs ──────────────────────────────────────────────────────
        rows = get_sqlite_rows(sqlite_conn, "reindex_jobs")
        count = 0
        for row in rows:
            job_id, client_slug, status, progress, started_at, completed_at, error, doc_count = row
            await pg.execute(
                """
                INSERT INTO reindex_jobs (job_id, client_slug, status, progress, started_at, completed_at, error, doc_count)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT DO NOTHING
                """,
                job_id,
                client_slug,
                status,
                progress,
                started_at,
                completed_at,
                error,
                doc_count,
            )
            count += 1
        totals["reindex_jobs"] = count

    finally:
        await pg.close()
        sqlite_conn.close()

    print("\nMigration complete. Rows migrated per table:")
    for table, n in totals.items():
        print(f"  {table:<20} {n}")


if __name__ == "__main__":
    asyncio.run(migrate())
