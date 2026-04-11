"""Unit tests for _build_drafting_section in arlc/agent/prompts.py.

Covers:
- FIRST-TURN MANDATE present when template selected and no documents exist
- Mandate absent when no template selected (research mode)
- chat_documents section indicates existing documents
- Czech date is locale-independent (no strftime %B)
"""

from __future__ import annotations

import os
import re

os.environ.setdefault("VERTEX_PROJECT_ID", "test-project")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from arlc.agent.prompts import (
    _CZECH_MONTHS,
    _build_drafting_section,
    _get_czech_date,
)


def _make_state(**kwargs) -> dict:
    base = {
        "template_slug": None,
        "template_name": None,
        "template_required_fields": [],
        "template_field_descriptions": {},
        "chat_documents": [],
    }
    base.update(kwargs)
    return base


def test_no_template_returns_empty():
    section = _build_drafting_section(_make_state())
    assert section == ""


def test_first_turn_mandate_present_on_new_conversation():
    state = _make_state(
        template_slug="zaloba-o-nahrade-skody", template_name="\u017daloba o n\u00e1hrad\u011b \u0161kody"
    )
    section = _build_drafting_section(state)
    assert "FIRST-TURN MANDATE" in section
    assert "document_draft" in section
    assert "action=create" in section


def test_mandate_uses_placeholder_language():
    state = _make_state(template_slug="zaloba-o-nahrade-skody")
    section = _build_drafting_section(state)
    assert "DOPLNIT" in section


def test_first_turn_mandate_comes_before_guardrails():
    state = _make_state(template_slug="zaloba-o-nahrade-skody")
    section = _build_drafting_section(state)
    mandate_pos = section.index("FIRST-TURN MANDATE")
    guardrails_pos = section.index("CRITICAL GUARDRAILS")
    assert mandate_pos < guardrails_pos


def test_existing_documents_listed_in_section():
    docs = [{"id": "uuid-abc", "template_slug": "z", "version": 2, "fields": {"claimant": "Jan Nov\u00e1k"}}]
    state = _make_state(template_slug="z", chat_documents=docs)
    section = _build_drafting_section(state)
    assert "uuid-abc" in section
    assert "action=update" in section


def test_no_documents_prompts_action_create():
    state = _make_state(template_slug="z", chat_documents=[])
    section = _build_drafting_section(state)
    assert "action=create" in section
    assert "No documents exist" in section


def test_czech_date_uses_czech_month_names():
    """_get_czech_date must return a Czech genitive month name regardless of server locale."""
    date_str = _get_czech_date()
    # Expected format: "D. <month> YYYY"
    match = re.fullmatch(r"\d{1,2}\. (\S+) \d{4}", date_str)
    assert match, f"Unexpected date format: {date_str!r}"
    assert match.group(1) in _CZECH_MONTHS, f"Month {match.group(1)!r} is not a Czech genitive month name"


def test_drafting_section_embeds_czech_date():
    """The DRAFTING MODE section must contain the locale-independent Czech date."""
    state = _make_state(template_slug="zaloba-o-nahrade-skody")
    section = _build_drafting_section(state)
    date_str = _get_czech_date()
    assert date_str in section, f"Expected Czech date {date_str!r} in drafting section"
