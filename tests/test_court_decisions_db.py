"""Tests for the court_decisions DB model and query helpers.

Requires a running PostgreSQL instance with the court_decisions table created.
Uses the test database (or the dev database) seeded with test fixtures.

Run with:
    uv run pytest tests/test_court_decisions_db.py -v
"""

from __future__ import annotations

from datetime import date

import pytest
import pytest_asyncio

# Use a session-scoped event loop so asyncpg connection pool connections
# remain valid across all tests in this module.  Without this, each test
# gets a new event loop, but asyncpg connections are bound to the loop from
# ensure_table's session fixture, causing "Future attached to a different loop".
# Note: individual @pytest.mark.asyncio decorators are intentionally omitted —
# asyncio_mode="auto" handles discovery, and pytestmark sets loop_scope.
pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def ensure_table():
    """Create the court_decisions table once per session."""
    from neolex.db.postgres import init_db

    await init_db()


@pytest.fixture
def sample_decision() -> dict:
    return {
        "ecli": "ECLI:CZ:NS:2023:21.CDO.1234.2023.1",
        "case_number": "21 Cdo 1234/2023",
        "court": "Nejvyssi soud",
        "decision_date": date(2023, 6, 15),
        "decision_type": "rozsudek",
        "category": "A",
        "legal_thesis": (
            "Zamestnavatel neni opravnen dat zamestnanci vypoved z duvodu "
            "nadbytecnosti, pokud pracovni misto nebylo skutecne zruseno. "
            "Zakonik prace par 52 odst. 1 pism. c."
        ),
        "judges": "JUDr. Jan Novak, JUDr. Marie Horakova",
        "source_url": "https://rozhodnuti.nsoud.cz/Judikatura/judikatura_ns.nsf/WebSearch/TESTUNID?openDocument",
        "source_unid": "TESTUNID",
        "regulations": [{"paragraph": "52", "law_number": 262, "law_year": 2006}],
        "keywords": ["vypoved", "nadbytecnost", "zakonik prace"],
    }


@pytest.fixture
def second_decision() -> dict:
    return {
        "ecli": "ECLI:CZ:NS:2022:21.CDO.5678.2022.1",
        "case_number": "21 Cdo 5678/2022",
        "court": "Nejvyssi soud",
        "decision_date": date(2022, 3, 10),
        "decision_type": "usneseni",
        "category": "B",
        "legal_thesis": (
            "Bezduvodne obohaceni vznika v okamziku, kdy jedna strana "
            "ziska majetkovy prospech bez pravniho duvodu na ukor druhe strany. "
            "Obcansky zakonik par 2991."
        ),
        "judges": "JUDr. Petra Svobodova",
        "source_url": "https://rozhodnuti.nsoud.cz/Judikatura/judikatura_ns.nsf/WebSearch/TESTUNID2?openDocument",
        "source_unid": "TESTUNID2",
        "regulations": [{"paragraph": "2991", "law_number": 89, "law_year": 2012}],
        "keywords": ["bezduvodni obohaceni", "obcansky zakonik"],
    }


async def test_upsert_insert(sample_decision):
    """Inserting a new decision creates a record."""
    from neolex.db.court_decisions import get_decision_by_ecli, upsert_decision

    # Use a unique ECLI so this test doesn't depend on cleanup order
    data = {**sample_decision, "ecli": "ECLI:CZ:NS:2023:21.CDO.1234.2023.INSERT_TEST"}
    record = await upsert_decision(data)
    assert record.ecli == data["ecli"]
    assert record.case_number == sample_decision["case_number"]
    assert record.category == "A"
    assert record.id is not None

    # Verify it's in the DB
    fetched = await get_decision_by_ecli(data["ecli"])
    assert fetched is not None
    assert fetched.case_number == sample_decision["case_number"]


async def test_upsert_update(sample_decision):
    """Upserting the same ECLI updates the existing record."""
    from neolex.db.court_decisions import get_decision_by_ecli, upsert_decision

    # First insert
    await upsert_decision(sample_decision)

    # Update with changed legal_thesis
    updated_data = {**sample_decision, "legal_thesis": "Aktualizovana pravni veta pro test."}
    record = await upsert_decision(updated_data)

    fetched = await get_decision_by_ecli(sample_decision["ecli"])
    assert fetched is not None
    assert fetched.legal_thesis == "Aktualizovana pravni veta pro test."
    # ID should be the same (updated, not re-inserted)
    assert fetched.id == record.id


async def test_upsert_missing_ecli_raises():
    """upsert_decision raises ValueError when ecli is missing."""
    from neolex.db.court_decisions import upsert_decision

    with pytest.raises(ValueError, match="ecli"):
        await upsert_decision({"case_number": "21 Cdo 9999/2024"})


async def test_upsert_missing_case_number_raises():
    """upsert_decision raises ValueError when case_number is missing."""
    from neolex.db.court_decisions import upsert_decision

    with pytest.raises(ValueError, match="case_number"):
        await upsert_decision({"ecli": "ECLI:CZ:NS:2024:TEST.1"})


async def test_bm25_search_finds_relevant(sample_decision):
    """BM25 search returns relevant results for Czech legal terms."""
    from neolex.db.court_decisions import search_decisions, upsert_decision

    # Ensure seeded
    await upsert_decision(sample_decision)

    results = await search_decisions("vypoved nadbytecnost zakonik prace")
    assert len(results) > 0
    eclis = [r.ecli for r in results]
    assert sample_decision["ecli"] in eclis


async def test_bm25_search_empty_query_returns_empty():
    """Empty query returns empty list without error."""
    from neolex.db.court_decisions import search_decisions

    results = await search_decisions("")
    assert results == []

    results = await search_decisions("   ")
    assert results == []


async def test_regulation_filter(sample_decision, second_decision):
    """statute_ref filter returns only decisions citing that statute."""
    from neolex.db.court_decisions import search_decisions, upsert_decision

    await upsert_decision(sample_decision)
    await upsert_decision(second_decision)

    # Filter by Labour Code (262/2006)
    results = await search_decisions("vypoved", statute_ref=(262, 2006))
    eclis = [r.ecli for r in results]
    assert sample_decision["ecli"] in eclis
    # Civil Code decision should NOT appear in Labour Code filter
    assert second_decision["ecli"] not in eclis


async def test_paragraph_filter(sample_decision, second_decision):
    """statute_ref 3-tuple filters to decisions citing a specific paragraph."""
    from neolex.db.court_decisions import search_decisions, upsert_decision

    await upsert_decision(sample_decision)  # regulations: [{paragraph: "52", law_number: 262, ...}]
    await upsert_decision(second_decision)  # regulations: [{paragraph: "2991", law_number: 89, ...}]

    # Matching paragraph: Labour Code § 52
    results = await search_decisions("vypoved", statute_ref=(262, 2006, "52"))
    eclis = [r.ecli for r in results]
    assert sample_decision["ecli"] in eclis

    # Wrong paragraph for the same statute: Labour Code § 53 → no match
    results_miss = await search_decisions("vypoved", statute_ref=(262, 2006, "53"))
    eclis_miss = [r.ecli for r in results_miss]
    assert sample_decision["ecli"] not in eclis_miss

    # Matching paragraph: Civil Code § 2991
    # Use multiple terms from legal_thesis + keywords for reliable BM25 match
    results_civil = await search_decisions("bezduvodni obohaceni obcansky zakonik", statute_ref=(89, 2012, "2991"))
    eclis_civil = [r.ecli for r in results_civil]
    assert second_decision["ecli"] in eclis_civil

    # Wrong paragraph for Civil Code: § 2079 → no match
    results_civil_miss = await search_decisions("bezduvodni obohaceni obcansky zakonik", statute_ref=(89, 2012, "2079"))
    eclis_civil_miss = [r.ecli for r in results_civil_miss]
    assert second_decision["ecli"] not in eclis_civil_miss


async def test_statute_filter_2tuple_still_works(sample_decision, second_decision):
    """2-tuple statute_ref (no paragraph) still works for backward compatibility."""
    from neolex.db.court_decisions import search_decisions, upsert_decision

    await upsert_decision(sample_decision)
    await upsert_decision(second_decision)

    # 2-tuple: Labour Code (all paragraphs)
    results = await search_decisions("vypoved", statute_ref=(262, 2006))
    eclis = [r.ecli for r in results]
    assert sample_decision["ecli"] in eclis


async def test_date_range_filter(sample_decision, second_decision):
    """date_from / date_to filters constrain results to the specified range."""
    from neolex.db.court_decisions import search_decisions, upsert_decision

    await upsert_decision(sample_decision)  # 2023-06-15
    await upsert_decision(second_decision)  # 2022-03-10

    # Only decisions from 2023 onward
    results_2023 = await search_decisions(
        "zakonik",
        date_from=date(2023, 1, 1),
    )
    eclis_2023 = [r.ecli for r in results_2023]
    assert sample_decision["ecli"] in eclis_2023
    assert second_decision["ecli"] not in eclis_2023

    # Only decisions before 2023
    results_old = await search_decisions(
        "obcansky zakonik",
        date_to=date(2022, 12, 31),
    )
    eclis_old = [r.ecli for r in results_old]
    assert second_decision["ecli"] in eclis_old
    assert sample_decision["ecli"] not in eclis_old


async def test_get_decisions_count_increases():
    """get_decisions_count returns a non-negative integer."""
    from neolex.db.court_decisions import get_decisions_count

    count = await get_decisions_count()
    assert isinstance(count, int)
    assert count >= 0


async def test_get_decision_by_ecli_not_found():
    """get_decision_by_ecli returns None for unknown ECLI."""
    from neolex.db.court_decisions import get_decision_by_ecli

    result = await get_decision_by_ecli("ECLI:CZ:NS:9999:DOES.NOT.EXIST.1")
    assert result is None
