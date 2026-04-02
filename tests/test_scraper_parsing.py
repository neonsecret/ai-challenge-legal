"""Tests for Czech Supreme Court scraper HTML parsers.

Uses real HTML fixtures saved from nsoud.cz.  No network calls.

Run with:
    uv run pytest tests/test_scraper_parsing.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_FIXTURES = Path(__file__).parent / "fixtures" / "nsoud"


@pytest.fixture(scope="session")
def search_html_2024_cat_a() -> str:
    f = _FIXTURES / "search_results_2024_cat_a.html"
    if not f.exists():
        pytest.skip("nsoud search fixture not available")
    return f.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def decision_html() -> str:
    f = _FIXTURES / "decision_009ED60B304444DAC1258BD90052AC8E.html"
    if not f.exists():
        pytest.skip("nsoud decision fixture not available")
    return f.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# parse_search_results
# ---------------------------------------------------------------------------


def test_parse_search_results_returns_list(search_html_2024_cat_a):
    from scripts.scrape_supreme_court import parse_search_results

    results = parse_search_results(search_html_2024_cat_a)
    assert isinstance(results, list)
    assert len(results) > 0, "Expected at least one result"


def test_parse_search_results_has_required_fields(search_html_2024_cat_a):
    from scripts.scrape_supreme_court import parse_search_results

    results = parse_search_results(search_html_2024_cat_a)
    first = results[0]
    assert "case_number" in first and first["case_number"]
    assert "source_unid" in first and len(first["source_unid"]) == 32
    assert "source_url" in first and "nsoud.cz" in first["source_url"]
    assert "ecli" in first and first["ecli"].startswith("NSOUD:")
    assert "court" in first and first["court"] == "Nejvyssi soud"


def test_parse_search_results_category(search_html_2024_cat_a):
    from scripts.scrape_supreme_court import parse_search_results

    results = parse_search_results(search_html_2024_cat_a)
    categories = {r.get("category") for r in results if r.get("category")}
    assert "A" in categories


def test_parse_search_results_legal_thesis_present(search_html_2024_cat_a):
    from scripts.scrape_supreme_court import parse_search_results

    results = parse_search_results(search_html_2024_cat_a)
    with_thesis = [r for r in results if r.get("legal_thesis")]
    assert len(with_thesis) > 0, "At least some results should have legal_thesis"


def test_parse_search_results_unid_is_hex(search_html_2024_cat_a):
    from scripts.scrape_supreme_court import parse_search_results

    results = parse_search_results(search_html_2024_cat_a)
    for r in results[:10]:
        unid = r["source_unid"]
        assert re.match(r"^[A-F0-9]{32}$", unid), f"UNID not valid: {unid!r}"


def test_parse_search_results_empty_html():
    from scripts.scrape_supreme_court import parse_search_results

    results = parse_search_results("<html><body><table></table></body></html>")
    assert results == []


# ---------------------------------------------------------------------------
# parse_decision_page
# ---------------------------------------------------------------------------


def test_parse_decision_page_ecli(decision_html):
    from scripts.scrape_supreme_court import parse_decision_page

    data = parse_decision_page(decision_html)
    assert "ecli" in data
    assert data["ecli"].startswith("ECLI:CZ:NS:")


def test_parse_decision_page_date(decision_html):
    from datetime import date

    from scripts.scrape_supreme_court import parse_decision_page

    data = parse_decision_page(decision_html)
    assert "decision_date" in data
    assert isinstance(data["decision_date"], date)
    assert data["decision_date"].year == 2024


def test_parse_decision_page_decision_type(decision_html):
    from scripts.scrape_supreme_court import parse_decision_page

    data = parse_decision_page(decision_html)
    assert "decision_type" in data
    assert data["decision_type"] in {"rozsudek", "usneseni"}


def test_parse_decision_page_regulations(decision_html):
    from scripts.scrape_supreme_court import parse_decision_page

    data = parse_decision_page(decision_html)
    if data.get("regulations"):
        laws = {r["law_number"] for r in data["regulations"]}
        # Fixture is a criminal case (trestní zákoník = 40/2009)
        assert 40 in laws, "Expected trestní zákoník (40/2009) reference"
        for reg in data["regulations"]:
            assert "law_number" in reg
            assert "law_year" in reg
            assert isinstance(reg["law_number"], int)


def test_parse_decision_page_full_text(decision_html):
    from scripts.scrape_supreme_court import parse_decision_page

    data = parse_decision_page(decision_html)
    if data.get("full_text"):
        assert len(data["full_text"]) > 50
        assert data.get("full_text_fetched") is True


# ---------------------------------------------------------------------------
# extract_regulations
# ---------------------------------------------------------------------------


def test_extract_regulations_official_format():
    from scripts.scrape_supreme_court import extract_regulations

    text = "Porušení dle § 52 z. č. 262/2006 Sb. zákoníku práce."
    regs = extract_regulations(text)
    assert any(r["law_number"] == 262 and r["law_year"] == 2006 for r in regs)


def test_extract_regulations_abbreviated_labour_code():
    from scripts.scrape_supreme_court import extract_regulations

    text = "§ 52 zákoníku práce stanovuje výpovědní důvody."
    regs = extract_regulations(text)
    labour = [r for r in regs if r["law_number"] == 262 and r["law_year"] == 2006]
    assert len(labour) > 0
    assert labour[0]["paragraph"] == "52"


def test_extract_regulations_criminal_code():
    from scripts.scrape_supreme_court import extract_regulations

    text = "§ 13 tr. zákoníku definuje trestný čin."
    regs = extract_regulations(text)
    criminal = [r for r in regs if r["law_number"] == 40 and r["law_year"] == 2009]
    assert len(criminal) > 0
    assert criminal[0]["paragraph"] == "13"


def test_extract_regulations_multiple():
    from scripts.scrape_supreme_court import extract_regulations

    text = "§ 52 zákoníku práce a § 2991 obč. zákoníku."
    regs = extract_regulations(text)
    law_numbers = {r["law_number"] for r in regs}
    assert 262 in law_numbers  # Labour Code
    assert 89 in law_numbers  # Civil Code


def test_extract_regulations_empty_text():
    from scripts.scrape_supreme_court import extract_regulations

    regs = extract_regulations("")
    assert regs == []

    regs = extract_regulations("Žádné právní normy zde.")
    assert regs == []


def test_extract_regulations_maps_to_corpus():
    """Extracted regulations should match our statute corpus entries."""
    from scripts.scrape_supreme_court import extract_regulations

    corpus_laws = {
        (89, 2012),  # Civil Code
        (40, 2009),  # Criminal Code
        (262, 2006),  # Labour Code
        (90, 2012),  # Business Corporations
        (500, 2004),  # Administrative Procedure
        (586, 1992),  # Income Tax
        (235, 2004),  # VAT
        (155, 1995),  # Pension Insurance
        (187, 2006),  # Sickness Insurance
        (455, 1991),  # Trade Licensing
    }
    text = "§ 52 zákoníku práce, § 2991 obč. zákoníku, § 13 tr. zákoníku"
    regs = extract_regulations(text)
    for reg in regs:
        pair = (reg["law_number"], reg["law_year"])
        assert pair in corpus_laws, f"Regulation {pair} not in our corpus"
