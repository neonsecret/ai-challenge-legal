"""Append-only PostgreSQL audit log using SQLAlchemy async.

AuditDB is the single interface for all operational database operations.
It is accessed through the get_audit_db() async context manager.
"""

import datetime as _dt
import json
from contextlib import asynccontextmanager

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from neolex.db.operational_models import (
    ApiKey,
    Document,
    Event,
    Query,
    RateLimit,
    ReindexJob,
)


def _to_dict(obj) -> dict:
    """Convert a SQLAlchemy model instance to a plain dict."""
    return {col.name: getattr(obj, col.name) for col in obj.__table__.columns}


class AuditDB:
    """Wrapper around an async SQLAlchemy session.

    Never instantiate directly — use get_audit_db() context manager.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def get_session(self) -> AsyncSession:
        """Return the underlying SQLAlchemy async session for raw query access."""
        return self._session

    # --- Schema (no-op — tables created by init_db()) ---

    async def init_schema(self) -> None:
        """No-op for PostgreSQL. Tables are created by init_db() at startup."""
        pass

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
        ts = _dt.datetime.now(_dt.UTC).isoformat()
        key = ApiKey(
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            client_slug=client_slug,
            scope=scope,
            active=True,
            created_at=ts,
        )
        self._session.add(key)
        await self._session.flush()
        return key.id

    async def get_key_by_hash(self, key_hash: str) -> dict | None:
        result = await self._session.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
        row = result.scalar_one_or_none()
        return _to_dict(row) if row else None

    async def list_keys(self) -> list[dict]:
        result = await self._session.execute(select(ApiKey).order_by(ApiKey.id))
        return [_to_dict(r) for r in result.scalars()]

    async def revoke_key(self, prefix: str) -> int:
        result = await self._session.execute(
            select(ApiKey).where(ApiKey.key_prefix == prefix, ApiKey.active == True),  # noqa: E712
        )
        rows = result.scalars().all()
        for row in rows:
            row.active = False
        return len(rows)

    async def update_last_used(self, key_id: int) -> None:
        result = await self._session.execute(select(ApiKey).where(ApiKey.id == key_id))
        key = result.scalar_one_or_none()
        if key:
            key.last_used = _dt.datetime.now(_dt.UTC).isoformat()

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
        self._session.add(
            Query(
                ts=_dt.datetime.now(_dt.UTC).isoformat(),
                key_hash=key_hash,
                question=question,
                answer_text=answer_text,
                sources_json=sources_json,
                latency_ms=latency_ms,
                model_name=model_name,
                ip=ip,
                user_agent=user_agent,
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
        self._session.add(
            Event(
                ts=_dt.datetime.now(_dt.UTC).isoformat(),
                key_hash=key_hash,
                event_type=event_type,
                detail_json=json.dumps(detail),
                ip=ip,
                user_agent=user_agent,
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
        self._session.add(
            ReindexJob(
                job_id=job_id,
                client_slug=client_slug,
                status="pending",
                progress=0.0,
                started_at=started_at,
            ),
        )

    async def get_reindex_job(self, job_id: str) -> dict | None:
        result = await self._session.execute(select(ReindexJob).where(ReindexJob.job_id == job_id))
        row = result.scalar_one_or_none()
        return _to_dict(row) if row else None

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
        result = await self._session.execute(select(ReindexJob).where(ReindexJob.job_id == job_id))
        job = result.scalar_one_or_none()
        if job:
            job.status = status
            job.progress = progress
            job.completed_at = completed_at
            job.error = error
            job.doc_count = doc_count

    # --- Document registry ---

    async def register_document(
        self,
        *,
        doc_id: str,
        client_slug: str,
        filename: str,
        size_bytes: int,
        upload_ts: str,
        file_type: str = "pdf",
    ) -> None:
        existing = await self._session.execute(
            select(Document).where(Document.doc_id == doc_id, Document.client_slug == client_slug),
        )
        if existing.scalar_one_or_none() is None:
            self._session.add(
                Document(
                    doc_id=doc_id,
                    client_slug=client_slug,
                    filename=filename,
                    size_bytes=size_bytes,
                    upload_ts=upload_ts,
                    indexed=False,
                    file_type=file_type,
                ),
            )

    async def get_document(self, doc_id: str, client_slug: str) -> dict | None:
        result = await self._session.execute(
            select(Document).where(Document.doc_id == doc_id, Document.client_slug == client_slug),
        )
        row = result.scalar_one_or_none()
        return _to_dict(row) if row else None

    async def list_documents(self, client_slug: str) -> list[dict]:
        result = await self._session.execute(
            select(Document).where(Document.client_slug == client_slug).order_by(Document.upload_ts.desc()),
        )
        return [_to_dict(r) for r in result.scalars()]

    async def mark_document_indexed(self, doc_id: str, client_slug: str) -> None:
        result = await self._session.execute(
            select(Document).where(Document.doc_id == doc_id, Document.client_slug == client_slug),
        )
        doc = result.scalar_one_or_none()
        if doc:
            doc.indexed = True

    async def delete_document(self, doc_id: str, client_slug: str) -> int:
        result = await self._session.execute(
            select(Document).where(Document.doc_id == doc_id, Document.client_slug == client_slug),
        )
        doc = result.scalar_one_or_none()
        if doc:
            await self._session.delete(doc)
            return 1
        return 0

    # --- Rate limiting ---

    async def check_and_increment_rate(
        self,
        bucket: str,
        window_seconds: float,
        limit: int,
        now: float,
    ) -> tuple[int, bool]:
        # Atomic upsert: insert first hit or reset+increment an expired window in one statement.
        # Eliminates TOCTOU race where two concurrent inserts both see count=0 and each write 1.
        result = await self._session.execute(
            text("""
                INSERT INTO rate_limits (bucket, window_start, request_count)
                VALUES (:bucket, :now, 1)
                ON CONFLICT (bucket) DO UPDATE SET
                    window_start = CASE
                        WHEN :now - rate_limits.window_start >= :window_seconds
                        THEN :now
                        ELSE rate_limits.window_start
                    END,
                    request_count = CASE
                        WHEN :now - rate_limits.window_start >= :window_seconds
                        THEN 1
                        ELSE rate_limits.request_count + 1
                    END
                RETURNING request_count
            """),
            {"bucket": bucket, "now": now, "window_seconds": window_seconds},
        )
        count: int = result.scalar_one()
        return count, count > limit

    async def get_ip_failure_count(self, bucket: str) -> tuple[int, float] | None:
        """Return (request_count, window_start) or None."""
        result = await self._session.execute(select(RateLimit).where(RateLimit.bucket == bucket))
        rl = result.scalar_one_or_none()
        if rl is None:
            return None
        return (rl.request_count, rl.window_start)

    # --- Audit log reads (admin use) ---

    async def get_queries(
        self,
        limit: int = 50,
        offset: int = 0,
        client_slug: str | None = None,
    ) -> list[dict]:
        if client_slug is None:
            result = await self._session.execute(select(Query).order_by(Query.id.desc()).limit(limit).offset(offset))
        else:
            result = await self._session.execute(
                select(Query)
                .join(ApiKey, ApiKey.key_hash == Query.key_hash)
                .where(ApiKey.client_slug == client_slug)
                .order_by(Query.id.desc())
                .limit(limit)
                .offset(offset),
            )
        return [_to_dict(r) for r in result.scalars()]

    async def get_events(
        self,
        limit: int = 50,
        offset: int = 0,
        client_slug: str | None = None,
    ) -> list[dict]:
        if client_slug is None:
            result = await self._session.execute(select(Event).order_by(Event.id.desc()).limit(limit).offset(offset))
        else:
            result = await self._session.execute(
                select(Event)
                .join(ApiKey, ApiKey.key_hash == Event.key_hash)
                .where(ApiKey.client_slug == client_slug)
                .order_by(Event.id.desc())
                .limit(limit)
                .offset(offset),
            )
        return [_to_dict(r) for r in result.scalars()]

    # --- Health check ---

    async def ping(self) -> None:
        """Verify DB connectivity with a lightweight query."""
        await self._session.execute(text("SELECT 1"))

    # --- Retention support ---

    async def count_purgeable(self, table: str, cutoff_iso: str) -> int:
        if table == "conversation_messages":
            from neolex.db.models import ConversationMessage

            result = await self._session.execute(
                select(func.count())
                .select_from(ConversationMessage)
                .where(ConversationMessage.created_at < cutoff_iso),
            )
            return result.scalar() or 0
        model = Query if table == "queries" else Event
        result = await self._session.execute(select(func.count()).select_from(model).where(model.ts < cutoff_iso))
        return result.scalar() or 0

    async def purge_table(self, table: str, cutoff_iso: str) -> int:
        if table == "conversation_messages":
            from neolex.db.models import ConversationMessage

            result = await self._session.execute(
                delete(ConversationMessage).where(ConversationMessage.created_at < cutoff_iso),
            )
            return result.rowcount
        model = Query if table == "queries" else Event
        result = await self._session.execute(delete(model).where(model.ts < cutoff_iso))
        return result.rowcount


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


@asynccontextmanager
async def get_audit_db():
    """Async context manager that yields an AuditDB instance.

    Commits on clean exit, rolls back on exception.

    Uses a lazy import of AsyncSessionLocal so that test fixtures that
    replace neolex.db.postgres.AsyncSessionLocal (e.g. install_null_pool_docs_engine)
    are always respected, even after module-level imports have frozen.
    """
    from neolex.db.postgres import AsyncSessionLocal as _SessionLocal  # lazy — always current

    async with _SessionLocal() as session:
        try:
            yield AuditDB(session)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
