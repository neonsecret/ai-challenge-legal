"""Explicit regression guards for known past bugs.

Each test targets a specific tracked regression:
  - NEO-2226: Czech query must NOT return DIFC documents
  - NEO-2184: Hybrid Czech + custom collection must NOT return zero jurisdiction results
  - NEO-2228: load_history must return NEWEST messages, not oldest
  - NEO-2232: Agent system prompt must acknowledge user documents in hybrid mode

NEO-2226 and NEO-2184 require the live stack and are marked @pytest.mark.e2e.
NEO-2228 and NEO-2232 are service-level tests that run without the HTTP backend.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import os  # noqa: E402

# Fallback env vars for CI environments where .env is absent.
# setdefault only writes when the key is not already set (load_dotenv above
# will have already populated these from .env on dev machines).
os.environ.setdefault("JWT_SECRET_KEY", "ci-test-only-secret-key-not-for-production")
os.environ.setdefault("ADMIN_EMAILS", "admin@vitreon.app")

# Only set a fallback DATABASE_URL when none is present (avoids overriding the
# real URL loaded from .env, which caused "role test does not exist" errors).
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test"),
)


# ---------------------------------------------------------------------------
# NEO-2228: load_history returns newest messages, not oldest
# ---------------------------------------------------------------------------


class TestLoadHistoryOrdering:
    """load_history must return the MOST RECENT MAX_HISTORY_TURNS messages.

    Bug (NEO-2228): load_history used ORDER BY created_at ASC with LIMIT N, returning
    the oldest N messages. When a conversation has >N messages the agent saw stale
    context instead of the recent exchange.

    Fix: ORDER BY created_at DESC + LIMIT N, then reversed() so the caller receives
    messages in chronological order (oldest→newest) but capped at the newest N.
    """

    def test_load_history_uses_desc_ordering(self):
        """NEO-2228 regression: load_history source must use DESC ordering before LIMIT.

        Inspects neolex/services/conversation.py directly.
        Fails immediately if the function reverts to ASC+LIMIT (oldest-first retrieval).
        """
        import inspect

        from neolex.services.conversation import load_history

        source = inspect.getsource(load_history)

        assert ".desc()" in source, (
            "NEO-2228 regression: load_history does not use .desc() ordering. "
            "ORDER BY created_at ASC + LIMIT returns the OLDEST messages. "
            "Fix: use .desc() before .limit() and reverse the result list."
        )
        assert "reversed(" in source, (
            "NEO-2228 regression: load_history uses .desc() but does not call reversed(). "
            "Without reversing, the agent receives messages newest-first instead of "
            "chronological order."
        )

    @pytest.mark.asyncio(loop_scope="session")
    async def test_load_history_empty_for_new_conversation(self):
        """load_history returns [] when no messages exist — not an error."""
        from neolex.services.conversation import load_history

        try:
            result = await load_history(str(uuid.uuid4()), str(uuid.uuid4()))
            assert result == [], f"Expected empty list, got {result}"
        except Exception as exc:
            exc_str = str(exc).lower()
            if any(kw in exc_str for kw in ("connect", "connection", "role")):
                pytest.skip(f"DB not reachable: {exc}")
            raise

    @pytest.mark.asyncio(loop_scope="session")
    async def test_load_history_empty_for_blank_conversation_id(self):
        """load_history returns [] for empty conversation_id without raising."""
        from neolex.services.conversation import load_history

        result = await load_history(str(uuid.uuid4()), "")
        assert result == []


# ---------------------------------------------------------------------------
# NEO-2232: Agent system prompt acknowledges user documents in hybrid mode
# ---------------------------------------------------------------------------


class TestAgentSystemPromptUserDocs:
    """build_system_prompt must include a user-documents notice when custom_corpus is set.

    Bug: Czech + custom collection mode — the system prompt did not tell the LLM
    that user documents were available. The agent responded "I cannot access your
    documents" instead of calling search_legal_corpus.

    Fix (commit 39da9ea): build_system_prompt checks state.get("custom_corpus") and
    state.get("custom_doc_ids") and injects an informational paragraph about the
    user's collection.
    """

    def _make_state(
        self,
        corpus: str,
        custom_corpus: str | None = None,
        custom_doc_ids: list | None = None,
    ) -> dict:
        return {
            "corpus": corpus,
            "selected_laws": [],
            "custom_corpus": custom_corpus,
            "custom_doc_ids": custom_doc_ids,
            "messages": [],
            "accumulated_docs": [],
            "search_count": 0,
            "user_id": "test-user",
            "conversation_id": "test-conv",
            "web_sources": [],
            "use_internet": False,
        }

    def test_hybrid_mode_system_prompt_mentions_user_documents(self):
        """Czech + custom corpus → system prompt must mention user's uploaded documents."""
        from arlc.agent.prompts import build_system_prompt

        state = self._make_state(
            corpus="czech",
            custom_corpus="user_client_slug",
            custom_doc_ids=["doc-uuid-1", "doc-uuid-2"],
        )
        prompt = build_system_prompt(state)

        assert any(kw in prompt.lower() for kw in ("uploaded", "personal", "collection", "user", "document")), (
            f"NEO-2232 regression: system prompt does not acknowledge user's custom documents.\n"
            f"Prompt (first 600 chars): {prompt[:600]}"
        )
        assert "upload documents" not in prompt.lower(), (
            "NEO-2232 regression: system prompt incorrectly says 'upload documents' "
            "when user already has documents available via search."
        )

    def test_corpus_only_mode_no_user_docs_notice(self):
        """Czech only (no custom corpus) → system prompt must NOT claim a personal collection."""
        from arlc.agent.prompts import build_system_prompt

        state = self._make_state(corpus="czech", custom_corpus=None, custom_doc_ids=None)
        prompt = build_system_prompt(state)

        assert "personal document collection" not in prompt.lower(), (
            "System prompt incorrectly mentions a personal collection for corpus-only mode."
        )

    def test_difc_hybrid_mode_acknowledges_user_collection(self):
        """DIFC + custom corpus → system prompt mentions the user's collection."""
        from arlc.agent.prompts import build_system_prompt

        state = self._make_state(
            corpus="difc",
            custom_corpus="user_slug",
            custom_doc_ids=["uuid-contract-1"],
        )
        prompt = build_system_prompt(state)

        assert any(kw in prompt.lower() for kw in ("uploaded", "collection", "document", "personal")), (
            f"DIFC hybrid mode system prompt does not acknowledge user's collection: {prompt[:500]}"
        )

    def test_custom_corpus_only_mode_system_prompt(self):
        """Custom corpus only (UUID-style slug) → prompt is non-empty."""
        from arlc.agent.prompts import build_system_prompt

        state = self._make_state(corpus="user_client_slug", custom_corpus=None, custom_doc_ids=None)
        prompt = build_system_prompt(state)
        assert len(prompt) > 50, "System prompt should not be empty"


# ---------------------------------------------------------------------------
# NEO-2226: Czech retrieval corpus isolation (live regression guard)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestNEO2226CzechCorpusIsolation:
    """Czech queries must never return DIFC documents.

    Bug: _doc_fusion_select hardcoded corpus='difc', returning DIFC chunks for Czech
    queries. Fix: corpus is passed dynamically through the retriever call chain.
    """

    @pytest.mark.asyncio(loop_scope="session")
    async def test_czech_statute_query_no_difc_docs(self, authed_client):
        """§ 52 Labour Code query → only Czech corpus sources."""
        from tests.e2e.conftest import stream_query

        result = await stream_query(
            authed_client,
            question="Co říká § 52 zákoníku práce o výpovědi ze strany zaměstnavatele?",
            corpus="czech",
        )
        doc_ids = [s.get("doc_id", "") for s in result.get("sources", []) if isinstance(s, dict)]
        assert doc_ids, "No sources — cannot assert corpus isolation"

        difc_docs = [d for d in doc_ids if "difc" in d.lower() or d.startswith("employment_law_difc")]
        assert not difc_docs, f"NEO-2226 regression: Czech § 52 query returned DIFC documents: {difc_docs}"

    @pytest.mark.asyncio(loop_scope="session")
    async def test_czech_civil_code_query_no_difc_docs(self, authed_client):
        """§ 2272 Civil Code query → only Czech corpus sources."""
        from tests.e2e.conftest import stream_query

        result = await stream_query(
            authed_client,
            question="Co upravuje § 2272 občanského zákoníku ohledně nájemní smlouvy?",
            corpus="czech",
        )
        doc_ids = [s.get("doc_id", "") for s in result.get("sources", []) if isinstance(s, dict)]
        assert doc_ids, "No sources — cannot assert corpus isolation"

        difc_docs = [d for d in doc_ids if "difc" in d.lower()]
        assert not difc_docs, f"NEO-2226 regression: Czech civil code query returned DIFC documents: {difc_docs}"


# ---------------------------------------------------------------------------
# NEO-2184: Hybrid mode must not return zero jurisdiction results
# ---------------------------------------------------------------------------


class TestNEO2184HybridJurisdictionResults:
    """Hybrid Czech + custom collection must return builtin corpus results.

    Bug: custom_doc_ids were being applied as a WHERE filter on the builtin corpus
    query, returning zero results because custom UUIDs don't exist in the builtin
    corpus table partition.

    Fix: custom_doc_ids are passed as a separate parameter; the builtin corpus
    search runs without any doc_ids filter.
    """

    @pytest.mark.asyncio(loop_scope="session")
    async def test_retriever_ignores_custom_doc_ids_for_builtin_corpus(self):
        """_retrieve_pages_simple with custom_doc_ids must still return builtin Czech results."""
        try:
            from arlc.retriever import _retrieve_pages_simple

            fake_uuid_doc_ids = [str(uuid.uuid4()) for _ in range(3)]
            results = _retrieve_pages_simple(
                question="výpověď zaměstnanec zákoník práce",
                corpus="czech",
                max_per_doc=1,
                max_total=5,
                answer_type="free_text",
                custom_corpus="fake_user_slug",
                custom_doc_ids=fake_uuid_doc_ids,
            )

            assert results, (
                "NEO-2184 regression: _retrieve_pages_simple returned zero results for Czech corpus "
                "when custom_doc_ids were provided. The builtin corpus search is likely filtering "
                "by custom_doc_ids instead of treating them as custom-corpus-only."
            )

            returned_ids = [getattr(r, "doc_id", None) for r in results]
            builtin_hits = [rid for rid in returned_ids if rid not in fake_uuid_doc_ids]
            assert builtin_hits, (
                f"NEO-2184 regression: all returned results are custom doc UUIDs — no builtin "
                f"Czech corpus results. IDs returned: {returned_ids}"
            )

        except (ModuleNotFoundError, ImportError) as exc:
            pytest.skip(f"Retriever module not importable: {exc}")
        except Exception as exc:
            exc_str = str(exc).lower()
            if any(kw in exc_str for kw in ("connect", "connection", "role", "embedding")):
                pytest.skip(f"DB/embedding server not reachable: {exc}")
            raise

    @pytest.mark.e2e
    @pytest.mark.asyncio(loop_scope="session")
    async def test_hybrid_query_returns_jurisdiction_sources_via_api(self, authed_client):
        """Czech corpus query via API must return jurisdiction sources.

        Proxy test for NEO-2184: if the retriever correctly ignores doc_id filtering
        for builtin corpora, a plain Czech query returns Czech statute results.
        """
        from tests.e2e.conftest import stream_query

        result = await stream_query(
            authed_client,
            question="Jaká jsou práva zaměstnance při výpovědi z pracovního poměru?",
            corpus="czech",
        )
        sources = result.get("sources", [])
        assert sources, "NEO-2184 regression proxy: Czech query returned no jurisdiction sources."

        czech_prefixes = ("zakonik", "zakon", "obcansky", "danovy", "trestni")
        czech_sources = [s for s in sources if isinstance(s, dict) and s.get("doc_id", "").startswith(czech_prefixes)]
        assert czech_sources, (
            f"NEO-2184: Czech query returned sources but none from Czech corpus: {[s.get('doc_id') for s in sources]}"
        )
