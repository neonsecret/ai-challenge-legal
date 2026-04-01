"""Failing integration tests for agent_v2.py — written BEFORE implementation.

Run before agent_v2.py exists:  uv run pytest tests/test_agent_v2.py -v
Expected: ImportError / FAIL on all 3 tests.

Run after implementation:
Expected: all 3 PASS.
"""

import json

from agent_v2 import answer_question


def load_warmup():
    qs = json.load(open("data/public_dataset.json"))
    # Dataset is a flat list with 'id' (not 'question_id')
    return qs["questions"] if isinstance(qs, dict) and "questions" in qs else qs


def test_law_article_question():
    """Law article questions should return non-null answer with at most 2 pages."""
    qs = load_warmup()
    law_q = next(q for q in qs if "Article" in q.get("question", "") and "Employment" in q.get("question", ""))
    result = answer_question(law_q)
    assert result["answer"] is not None
    assert len(result["chunk_pages"]) >= 1
    # Single law question should cite at most 2 pages
    total_pages = sum(len(c["page_numbers"]) for c in result["chunk_pages"])
    assert total_pages <= 2


def test_boolean_returns_bool():
    """Boolean questions should return a Python bool (or None)."""
    qs = load_warmup()
    bool_q = next(q for q in qs if q.get("answer_type") == "boolean")
    result = answer_question(bool_q)
    assert isinstance(result["answer"], bool) or result["answer"] is None


def test_confidence_in_result():
    """Every result must have a confidence score in [0, 1]."""
    qs = load_warmup()
    result = answer_question(qs[0])
    assert "confidence" in result
    assert 0.0 <= result["confidence"] <= 1.0
