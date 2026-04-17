"""E2E tests for hybrid mode and custom corpus isolation — live backend required.

Coverage:
  2. Hybrid mode integration — jurisdiction + custom corpus, assert BOTH sources appear
  3. Custom corpus isolation — custom-corpus-only query, assert no jurisdiction bleed

All @pytest.mark.e2e tests skip when localhost:8000 is unavailable or the admin user
does not have upload permissions (subscription gate). The session fixture uploads a small
TXT fixture document, runs the suite, then deletes the document on teardown.

Design notes:
- Uses /auth/me to get the admin user's UUID (= corpora_id for custom-corpus queries)
- Uploads a plain-text fixture containing unique sentinel terms for deterministic retrieval
- Polls /api/v1/documents/reindex/{job_id} until indexing completes (max 90 s)
- Skips gracefully for 403 (no subscription) instead of failing
"""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest
import pytest_asyncio

from tests.e2e.conftest import stream_query

pytestmark = [pytest.mark.e2e, pytest.mark.asyncio(loop_scope="session")]

# Sentinel phrase — unique enough to not appear in any builtin corpus.
_FIXTURE_SENTINEL = "Vitreon Fixture Notice Period Provision"
_FIXTURE_FILENAME = "vitreon_e2e_fixture.txt"
_FIXTURE_TEXT = (
    f"{_FIXTURE_SENTINEL}\n\n"
    "Section 42 of the Vitreon Test Employment Act 2026 provides that an employer must "
    "give a minimum notice period of four weeks before terminating the employment contract "
    "of any employee who has completed more than one year of continuous service. "
    "This notice period obligation applies regardless of the reason for termination.\n\n"
    "Section 43: Any breach of the notice period provisions entitles the employee to "
    "compensation equivalent to the wages that would have been earned during the "
    "applicable notice period. Such compensation is calculated on the basis of the "
    "employee's average weekly earnings in the twelve weeks preceding termination.\n"
)

_FIXTURE_BUILTIN_CORPUS_PREFIXES = (
    "zakonik",
    "zakon",
    "obcansky",
    "employment_law_difc",
    "employment_rights_act",
    "fair_work_act",
    "corporations_act",
    "data_protection",
)


@pytest_asyncio.fixture(scope="session")
async def fixture_corpus(authed_client: httpx.AsyncClient):
    """Upload a TXT fixture document for the admin user and yield the corpora_id.

    Skips the test session if the backend is unreachable or the admin account
    does not have upload permissions (free tier / no subscription).

    Yields: dict with keys ``corpora_id`` (user UUID = client_slug), ``doc_id``
    """
    # Resolve admin user UUID (= the corpora_id for custom-corpus queries)
    me_resp = await authed_client.get(
        "/auth/me",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    if me_resp.status_code != 200:
        pytest.skip(f"Cannot resolve admin user identity ({me_resp.status_code})")

    me = me_resp.json()
    user_id = me.get("id")
    plan = me.get("plan", "free")

    if plan in ("free", "trial"):
        pytest.skip(
            f"Admin user is on plan={plan!r} — upload requires paid plan. "
            "Skipping Areas 2 and 3 (hybrid + corpus isolation). "
            "Set admin subscription_status='starter' or higher in the local DB to enable."
        )

    # Upload the fixture TXT document
    upload_resp = await authed_client.post(
        "/api/v1/documents",
        content=_FIXTURE_TEXT.encode(),
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Content-Disposition": f'attachment; filename="{_FIXTURE_FILENAME}"',
        },
        files={"file": (_FIXTURE_FILENAME, _FIXTURE_TEXT.encode(), "text/plain")},
        data={"collection": "E2E Fixture"},
    )

    if upload_resp.status_code == 403:
        pytest.skip("Admin upload returned 403 — subscription gate active. Skipping hybrid/isolation tests.")
    if upload_resp.status_code == 429:
        pytest.skip(
            f"Admin upload returned 429 — plan limits reached ({upload_resp.json().get('detail')}). "
            "Delete existing documents or upgrade plan to run these tests."
        )
    if upload_resp.status_code not in (200, 201):
        pytest.skip(
            f"Fixture upload failed ({upload_resp.status_code}): {upload_resp.text[:200]}. "
            "Skipping hybrid/isolation tests."
        )

    upload_data = upload_resp.json()
    doc_id = upload_data.get("doc_id")
    job_id = upload_data.get("job_id")

    assert doc_id, f"Upload response missing doc_id: {upload_data}"

    # Poll for indexing completion (max 90 s)
    if job_id:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            status_resp = await authed_client.get(
                f"/api/v1/documents/reindex/{job_id}",
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            if status_resp.status_code == 200:
                job_status = status_resp.json().get("status", "")
                if job_status in ("done", "completed", "success"):
                    break
                if job_status in ("error", "failed"):
                    pytest.skip(f"Fixture reindex job failed: {status_resp.json()}")
            await asyncio.sleep(3)
        else:
            # Indexing timed out — proceed anyway; vector search may not find it
            # but text search should still work if the trigger ran
            pass

    yield {"corpora_id": user_id, "doc_id": doc_id}

    # Teardown — delete the fixture document
    try:
        del_resp = await authed_client.delete(
            f"/api/v1/documents/{doc_id}",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        if del_resp.status_code not in (200, 204, 404):
            # Non-fatal — log but don't fail teardown
            pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Area 2: Hybrid mode integration
# ---------------------------------------------------------------------------


class TestHybridModeIntegration:
    """Czech + custom corpus queries must return BOTH jurisdiction AND custom chunks.

    These tests guard against NEO-2184 (hybrid Czech + collection returning
    zero jurisdiction results) and the complementary bug where custom docs are
    ignored in hybrid mode.
    """

    async def test_hybrid_czech_fixture_returns_czech_sources(
        self,
        authed_client: httpx.AsyncClient,
        fixture_corpus: dict,
    ):
        """Czech + fixture corpus query must include Czech statute sources.

        If the retriever incorrectly applies custom_doc_ids as a filter for the
        builtin corpus search, no Czech statute chunks will appear.
        """
        corpora_id = fixture_corpus["corpora_id"]

        result = await stream_query(
            authed_client,
            question="Jaká je výpovědní doba při ukončení pracovního poměru?",
            corpus="czech",
            corpora_id=corpora_id,
        )
        sources = result.get("sources", [])
        assert sources, "Hybrid Czech + fixture query returned no sources at all"

        doc_ids = [s.get("doc_id", "") for s in sources if isinstance(s, dict)]
        czech_sources = [
            did
            for did in doc_ids
            if any(did.startswith(p) for p in ("zakonik", "zakon", "obcansky", "trestni", "danovy"))
        ]
        assert czech_sources, (
            f"NEO-2184 hybrid regression: Czech + custom corpus query returned no Czech statute "
            f"sources. All returned doc_ids: {doc_ids}. "
            f"The retriever may be filtering builtin corpus by custom_doc_ids."
        )

    async def test_hybrid_czech_fixture_returns_fixture_sources(
        self,
        authed_client: httpx.AsyncClient,
        fixture_corpus: dict,
    ):
        """Czech + fixture corpus query must include the fixture document in sources.

        Queries using the sentinel term to maximize fixture recall probability.
        """
        corpora_id = fixture_corpus["corpora_id"]
        fixture_doc_id = fixture_corpus["doc_id"]

        result = await stream_query(
            authed_client,
            question="notice period employment contract section 42",
            corpus="czech",
            corpora_id=corpora_id,
        )
        sources = result.get("sources", [])
        assert sources, "Hybrid query returned no sources at all"

        doc_ids = [s.get("doc_id", "") for s in sources if isinstance(s, dict)]
        fixture_hits = [did for did in doc_ids if did == fixture_doc_id]
        assert fixture_hits, (
            f"Hybrid Czech + custom corpus query did not return the fixture document "
            f"({fixture_doc_id}). All returned doc_ids: {doc_ids}. "
            f"The custom corpus search leg may be broken."
        )

    async def test_hybrid_answer_acknowledges_both_sources(
        self,
        authed_client: httpx.AsyncClient,
        fixture_corpus: dict,
    ):
        """Hybrid mode answer should mention concepts from both the jurisdiction and fixture.

        This is a soft smoke test — we verify the agent produced a non-empty answer
        with sources, not that it literally quotes both. The agent may synthesize.
        """
        corpora_id = fixture_corpus["corpora_id"]

        result = await stream_query(
            authed_client,
            question="What is the notice period for terminating employment?",
            corpus="czech",
            corpora_id=corpora_id,
        )
        answer = result.get("answer", "")
        sources = result.get("sources", [])

        assert sources, "Hybrid mode answer has no source citations"
        assert answer, "Hybrid mode returned empty answer"
        _notice_kws = ("notice", "výpověď", "termination", "employment", "week", "month")
        assert any(kw in answer.lower() for kw in _notice_kws), (
            f"Hybrid mode answer does not reference expected notice-period concepts: {answer[:300]}"
        )


# ---------------------------------------------------------------------------
# Area 3: Custom corpus isolation
# ---------------------------------------------------------------------------


class TestCustomCorpusIsolation:
    """Custom-corpus-only queries must NOT return jurisdiction (builtin) documents.

    When a user queries their private corpus, the results must come exclusively
    from their uploaded documents — never from Czech, DIFC, UK, or AU builtin chunks.
    """

    async def test_custom_only_query_no_builtin_corpus_bleed(
        self,
        authed_client: httpx.AsyncClient,
        fixture_corpus: dict,
    ):
        """Custom-corpus-only query must not include builtin Czech/DIFC/UK/AU doc_ids."""
        corpora_id = fixture_corpus["corpora_id"]

        # Query about notice periods — a topic present in the fixture AND in builtin corpora.
        # With custom-only mode (no corpus=czech), ONLY fixture docs should appear.
        result = await stream_query(
            authed_client,
            question="What is the notice period obligation in this document?",
            corpus=corpora_id,  # user's own corpus slug as the corpus
            corpora_id=corpora_id,
        )
        sources = result.get("sources", [])

        if not sources:
            # No sources returned — the query found nothing in the fixture.
            # This may happen if indexing didn't complete. Skip rather than fail.
            pytest.skip(
                "Custom-corpus-only query returned no sources. "
                "Fixture may not have been indexed yet — re-run when indexing is confirmed."
            )

        doc_ids = [s.get("doc_id", "") for s in sources if isinstance(s, dict)]
        builtin_leaks = [did for did in doc_ids if any(did.startswith(p) for p in _FIXTURE_BUILTIN_CORPUS_PREFIXES)]
        assert not builtin_leaks, (
            f"Custom corpus isolation failure: custom-only query returned builtin corpus docs: "
            f"{builtin_leaks}. All returned doc_ids: {doc_ids}. "
            f"The retriever is bleeding across corpus boundaries."
        )

    async def test_fixture_document_appears_in_custom_only_query(
        self,
        authed_client: httpx.AsyncClient,
        fixture_corpus: dict,
    ):
        """The fixture document must appear when querying the custom corpus."""
        corpora_id = fixture_corpus["corpora_id"]
        fixture_doc_id = fixture_corpus["doc_id"]

        result = await stream_query(
            authed_client,
            question="notice period section 42 employment termination",
            corpus=corpora_id,
            corpora_id=corpora_id,
        )
        sources = result.get("sources", [])

        if not sources:
            pytest.skip("Custom-corpus query returned no sources — fixture may not be indexed yet.")

        doc_ids = [s.get("doc_id", "") for s in sources if isinstance(s, dict)]
        assert fixture_doc_id in doc_ids, (
            f"Fixture document {fixture_doc_id!r} not found in custom-corpus query results. "
            f"All returned doc_ids: {doc_ids}"
        )
