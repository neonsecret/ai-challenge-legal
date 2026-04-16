"""Unit tests for neolex.indexing.reindex_worker.

Tests cover:
- _run_indexing_sync: non-HTTP-400 exceptions propagate (no silent stub).
- _run_indexing_sync: HTTP 400 from llama-server stubs and returns (doc_count, 1).
- run_reindex_job: if _run_indexing_sync raises, the job is marked "failed".

No real database or filesystem I/O is performed — all external dependencies
are mocked via unittest.mock.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
import requests.exceptions

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_http_error(status_code: int) -> requests.exceptions.HTTPError:
    """Build a requests.HTTPError with the given status code."""
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    err = requests.exceptions.HTTPError(response=response)
    return err


# ---------------------------------------------------------------------------
# Tests for _run_indexing_sync
# ---------------------------------------------------------------------------


class TestRunIndexingSync:
    """_run_indexing_sync must propagate non-400 errors and stub only on HTTP 400."""

    def test_reindex_failure_propagates(self, tmp_path: Path):
        """A generic Exception from _run_arlc_indexing must propagate — no silent stub."""
        from neolex.indexing.reindex_worker import _run_indexing_sync

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        index_dir = tmp_path / "index"
        index_dir.mkdir()

        generic_error = RuntimeError("DB connection refused")

        with patch("neolex.indexing.reindex_worker._run_arlc_indexing", side_effect=generic_error):
            with pytest.raises(RuntimeError, match="DB connection refused"):
                _run_indexing_sync("test-client", docs_dir, index_dir)

        # No manifest should have been written
        assert not (index_dir / "manifest.json").exists()

    def test_import_error_propagates(self, tmp_path: Path):
        """ImportError (arlc not installed) must also propagate — no silent stub."""
        from neolex.indexing.reindex_worker import _run_indexing_sync

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        index_dir = tmp_path / "index"
        index_dir.mkdir()

        with patch(
            "neolex.indexing.reindex_worker._run_arlc_indexing",
            side_effect=ImportError("No module named 'arlc.indexing.indexer'"),
        ):
            with pytest.raises(ImportError):
                _run_indexing_sync("test-client", docs_dir, index_dir)

        assert not (index_dir / "manifest.json").exists()

    def test_reindex_http400_raises(self, tmp_path: Path):
        """HTTP 400 from llama-server must raise RuntimeError, not stub.

        Previously this wrote a stub manifest claiming N docs were indexed
        while zero embeddings were written — retrieval silently returned nothing.
        The correct behavior is to fail loudly with a clear message so the user
        knows to split large documents.
        """
        from neolex.indexing.reindex_worker import _run_indexing_sync

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        index_dir = tmp_path / "index"
        index_dir.mkdir()

        http_400 = _make_http_error(400)

        with patch("neolex.indexing.reindex_worker._run_arlc_indexing", side_effect=http_400):
            with pytest.raises(RuntimeError, match="context window"):
                _run_indexing_sync("test-client", docs_dir, index_dir)

        # No stub manifest should be written — the job failed
        assert not (index_dir / "manifest.json").exists()

    def test_reindex_http_non_400_propagates(self, tmp_path: Path):
        """HTTP 503 (or any non-400) from llama-server must re-raise, not stub."""
        from neolex.indexing.reindex_worker import _run_indexing_sync

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        index_dir = tmp_path / "index"
        index_dir.mkdir()

        http_503 = _make_http_error(503)

        with patch("neolex.indexing.reindex_worker._run_arlc_indexing", side_effect=http_503):
            with pytest.raises(requests.exceptions.HTTPError):
                _run_indexing_sync("test-client", docs_dir, index_dir)

        assert not (index_dir / "manifest.json").exists()


# ---------------------------------------------------------------------------
# Tests for run_reindex_job
# ---------------------------------------------------------------------------


class TestRunReindexJob:
    """run_reindex_job must mark the job 'failed' if _run_indexing_sync raises."""

    @pytest.mark.asyncio
    async def test_reindex_job_fails_on_exception(self, tmp_path: Path):
        """When _run_indexing_sync raises, the job status must be set to 'failed'."""
        from neolex.indexing.reindex_worker import run_reindex_job

        job_id = "test-job-001"
        client_slug = "test-client"

        # Track calls to update_job
        update_calls: list[dict] = []

        async def fake_update_job(jid, *, status, progress=0.0, completed_at=None, error=None, doc_count=0):
            update_calls.append({"job_id": jid, "status": status, "error": error})

        # _run_indexing_sync raises; to_thread forwards the exception to the coroutine
        async def fake_to_thread(fn, *args, **kwargs):
            raise RuntimeError("Simulated indexing failure")

        # client_docs_dir / client_index_dir return tmp dirs
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        index_dir = tmp_path / "index"
        index_dir.mkdir()

        with (
            patch("neolex.indexing.reindex_worker.update_job", side_effect=fake_update_job),
            patch("neolex.indexing.reindex_worker.client_docs_dir", return_value=docs_dir),
            patch("neolex.indexing.reindex_worker.client_index_dir", return_value=index_dir),
            patch("asyncio.to_thread", side_effect=fake_to_thread),
        ):
            await run_reindex_job(job_id, client_slug, app=None)

        # The last call must be status="failed"
        assert update_calls, "update_job was never called"
        final_call = update_calls[-1]
        assert final_call["status"] == "failed", (
            f"Expected status='failed' but got status='{final_call['status']}'. All update_job calls: {update_calls}"
        )
