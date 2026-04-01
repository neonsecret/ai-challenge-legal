"""Tests for new tools in agent_tools.py — Task 3 of agentic RAG v2 plan."""

import json

from agent_tools import (
    get_case_metadata,
    get_latest_law_doc,
    search_within_doc,
    verify_page_supports_answer,
)


def test_search_within_doc_returns_pages():
    """BM25 search within a real law doc returns ranked pages."""
    idx = json.load(open("data/article_page_index.json"))
    law_doc = next(k for k, v in idx.items() if v.get("type") == "LAW")
    results = search_within_doc(law_doc, "article", top_k=3)
    assert isinstance(results, list)
    assert len(results) > 0
    assert "page_num" in results[0]
    assert "text" in results[0]


def test_search_within_doc_empty_for_fake_doc():
    """search_within_doc returns empty list for non-existent doc."""
    results = search_within_doc("0" * 64, "anything", top_k=3)
    assert results == []


def test_get_case_metadata_returns_none_for_unknown():
    """get_case_metadata with field returns None when case not in index."""
    result = get_case_metadata("FAKE 999/9999", "judge")
    assert result is None


def test_get_case_metadata_backward_compat():
    """get_case_metadata with no field arg still works (backward compat)."""
    result = get_case_metadata("FAKE 999/9999")
    # Old behavior: returns empty dict or None, not an exception
    assert result is None or isinstance(result, dict)


def test_get_latest_law_doc_returns_doc_id():
    """get_latest_law_doc returns a SHA256-length doc_id for known law."""
    doc_id = get_latest_law_doc("employment law")
    assert doc_id is not None
    assert len(doc_id) > 10  # SHA256 hash


def test_get_latest_law_doc_returns_none_for_unknown():
    """get_latest_law_doc returns None for completely unknown law."""
    doc_id = get_latest_law_doc("fake law that does not exist xyz123")
    assert doc_id is None


def test_verify_page_supports_answer_structure():
    """verify_page_supports_answer returns dict with required keys."""
    # Use a fake doc_id — should return unsupported with 0 confidence
    result = verify_page_supports_answer(
        doc_id="0" * 64,
        page_num=1,
        question="What is the notice period?",
        answer="30 days",
    )
    assert isinstance(result, dict)
    assert "supported" in result
    assert "confidence" in result
    assert "explanation" in result
    assert isinstance(result["supported"], bool)
    assert 0.0 <= result["confidence"] <= 1.0


def test_verify_page_supports_answer_empty_page():
    """verify_page_supports_answer handles empty/missing page gracefully."""
    result = verify_page_supports_answer(
        doc_id="0" * 64,
        page_num=1,
        question="anything",
        answer="anything",
    )
    assert result["supported"] is False
    assert result["confidence"] == 0.0
