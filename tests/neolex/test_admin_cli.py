"""Admin CLI tests (AUTH-04) and Phase 2 integration smoke test.

CLI functions are tested by calling cmd_* handlers directly (not via subprocess)
to avoid process-level setup and keep tests fast. The integration test exercises
the full cycle: CLI creates key -> server validates it -> audit log captures query.
"""
import argparse
import asyncio
import io
import sys
import pytest

from neolex.admin import cmd_keys_create, cmd_keys_list, cmd_keys_revoke, cmd_show_log


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ns(**kwargs) -> argparse.Namespace:
    """Create a minimal argparse.Namespace for testing."""
    return argparse.Namespace(**kwargs)


# ---------------------------------------------------------------------------
# keys-create
# ---------------------------------------------------------------------------

async def test_create_key_roundtrip(tmp_db_path, monkeypatch, capsys):
    """keys-create inserts a row into api_keys with correct fields."""
    from neolex.config import settings
    monkeypatch.setattr(settings, "db_path", tmp_db_path)
    from neolex.db.audit import get_audit_db

    args = make_ns(name="Test Client", client_slug="test-co", scope="query")
    await cmd_keys_create(args)

    async with get_audit_db() as db:
        rows = await db.list_keys()

    assert len(rows) == 1
    row = dict(rows[0])
    assert row["name"] == "Test Client"
    assert row["client_slug"] == "test-co"
    assert row["scope"] == "query"
    assert row["active"] == 1
    assert len(row["key_hash"]) == 64  # SHA-256 hex
    assert len(row["key_prefix"]) == 8


async def test_create_key_prints_plaintext(tmp_db_path, monkeypatch, capsys):
    """keys-create prints the raw plaintext key to stdout exactly once."""
    from neolex.config import settings
    monkeypatch.setattr(settings, "db_path", tmp_db_path)

    args = make_ns(name="Print Test", client_slug="print-test", scope="query")
    await cmd_keys_create(args)

    captured = capsys.readouterr()
    assert "KEY:" in captured.out
    assert "SAVE THIS KEY" in captured.out
    # Extract the key line
    for line in captured.out.splitlines():
        if line.strip().startswith("KEY:"):
            raw_key = line.split("KEY:")[-1].strip()
            assert len(raw_key) == 43, f"Expected 43-char key, got {len(raw_key)}: {raw_key}"
            break
    else:
        pytest.fail("KEY line not found in output")


async def test_create_admin_key(tmp_db_path, monkeypatch, capsys):
    """keys-create --scope admin creates an admin-scoped key."""
    from neolex.config import settings
    monkeypatch.setattr(settings, "db_path", tmp_db_path)
    from neolex.db.audit import get_audit_db

    args = make_ns(name="Admin Key", client_slug="admin", scope="admin")
    await cmd_keys_create(args)

    async with get_audit_db() as db:
        rows = await db.list_keys()

    assert dict(rows[0])["scope"] == "admin"


# ---------------------------------------------------------------------------
# keys-list
# ---------------------------------------------------------------------------

async def test_list_keys(tmp_db_path, monkeypatch, capsys):
    """keys-list after creating a key prints key name."""
    from neolex.config import settings
    monkeypatch.setattr(settings, "db_path", tmp_db_path)

    # Create a key first
    await cmd_keys_create(make_ns(name="ListTest", client_slug="list-co", scope="query"))
    capsys.readouterr()  # clear create output

    await cmd_keys_list(make_ns())
    captured = capsys.readouterr()
    assert "ListTest" in captured.out


# ---------------------------------------------------------------------------
# keys-revoke
# ---------------------------------------------------------------------------

async def test_revoke_key(tmp_db_path, monkeypatch, capsys):
    """keys-revoke marks key inactive; second revoke reports 0 affected."""
    from neolex.config import settings
    monkeypatch.setattr(settings, "db_path", tmp_db_path)
    from neolex.db.audit import get_audit_db

    # Create a key and capture its prefix
    await cmd_keys_create(make_ns(name="RevokeMe", client_slug="revoke-co", scope="query"))
    async with get_audit_db() as db:
        rows = await db.list_keys()
    prefix = dict(rows[0])["key_prefix"]

    capsys.readouterr()  # clear

    # Revoke it
    await cmd_keys_revoke(make_ns(prefix=prefix))
    out = capsys.readouterr().out
    assert "Revoked 1" in out

    # Verify in DB
    async with get_audit_db() as db:
        rows = await db.list_keys()
    assert dict(rows[0])["active"] == 0

    # Second revoke returns 0
    with pytest.raises(SystemExit) as exc_info:
        await cmd_keys_revoke(make_ns(prefix=prefix))
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# show-log
# ---------------------------------------------------------------------------

async def test_show_log_empty(tmp_db_path, monkeypatch, capsys):
    """show-log on empty DB prints 'No entries' message."""
    from neolex.config import settings
    monkeypatch.setattr(settings, "db_path", tmp_db_path)

    await cmd_show_log(make_ns(table="queries", limit=20))
    captured = capsys.readouterr()
    assert "No entries" in captured.out


async def test_show_log_after_query(tmp_db_path, monkeypatch, capsys):
    """show-log shows entry after log_query is called."""
    from neolex.config import settings
    monkeypatch.setattr(settings, "db_path", tmp_db_path)
    from neolex.db.audit import get_audit_db

    async with get_audit_db() as db:
        await db.init_schema()
        await db.log_query(
            key_hash="abc" * 21 + "a",
            question="What is the limitation period?",
            answer_text="6 years",
            sources_json="[]",
            latency_ms=1234,
            model_name="claude-sonnet-4-6",
            ip="127.0.0.1",
            user_agent="test",
        )

    await cmd_show_log(make_ns(table="queries", limit=5))
    captured = capsys.readouterr()
    assert "limitation period" in captured.out
    assert "1234" in captured.out  # latency visible in output


# ---------------------------------------------------------------------------
# Phase 2 integration smoke test
# ---------------------------------------------------------------------------

@pytest.mark.integration
async def test_full_phase2_cycle(tmp_db_path, monkeypatch):
    """Full Phase 2 cycle: create key -> authenticate -> query -> audit log entry.

    This test requires no live LLM or corpus — the pipeline is mocked.
    It exercises the full HTTP stack including auth middleware and audit logging.
    """
    import asyncio
    import json as _json
    from unittest.mock import AsyncMock, MagicMock, patch
    from httpx import AsyncClient, ASGITransport
    from neolex.config import settings
    from neolex.main import app
    from neolex.db.audit import get_audit_db

    monkeypatch.setattr(settings, "db_path", tmp_db_path)

    # Step 1: Create a query-scoped key via CLI
    import io as _io
    from contextlib import redirect_stdout
    buf = _io.StringIO()
    with redirect_stdout(buf):
        await cmd_keys_create(make_ns(name="Integration Key", client_slug="integ-co", scope="query"))
    output = buf.getvalue()

    # Extract raw key from CLI output
    raw_key = None
    for line in output.splitlines():
        if line.strip().startswith("KEY:"):
            raw_key = line.split("KEY:")[-1].strip()
            break
    assert raw_key is not None, "CLI did not print raw key"
    assert len(raw_key) == 43

    # Step 2: Set up mocked FastAPI app
    mock_result = {
        "id": "integ-001",
        "question": "What is the limitation period?",
        "answer_type": "free_text",
        "answer": "The limitation period is 6 years.",
        "chunk_pages": [{"doc_id": "DIFC-LAW-5-2005", "page_numbers": [12]}],
        "ttft_ms": 500,
        "tpot_ms": 10.0,
        "total_time_ms": 2800,
        "input_tokens": 1500,
        "output_tokens": 60,
        "model_name": "claude-sonnet-4-6",
    }

    app.state.ready = True
    app.state.semaphore = asyncio.Semaphore(5)
    app.state.workers = 5
    app.state.route_fn = MagicMock()
    app.state.retrieve_fn = MagicMock()
    app.state.answer_fn = MagicMock()

    with patch(
            "neolex.routers.query.run_single_question",
            new_callable=AsyncMock,
            return_value=mock_result,
    ):
        async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Step 3: Authenticate and query
            response = await client.post(
                "/api/v1/query",
                json={"question": "What is the limitation period?", "answer_type": "free_text"},
                headers={"Authorization": f"Bearer {raw_key}"},
            )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["answer"] == "The limitation period is 6 years."

    # Step 4: Verify audit trail
    async with get_audit_db() as db:
        query_rows = await db.get_queries(limit=5)

    assert len(query_rows) >= 1, "No query rows found in audit log"
    last_query = dict(query_rows[0])
    assert "limitation period" in last_query["question"]
    assert last_query["latency_ms"] == 2800
    assert last_query["model_name"] == "claude-sonnet-4-6"

    # Step 5: Verify key last_used was updated
    from neolex.auth.keys import hash_key
    k_hash = hash_key(raw_key)
    async with get_audit_db() as db:
        key_row = await db.get_key_by_hash(k_hash)
    assert dict(key_row)["last_used"] is not None, "last_used not updated after successful auth"
