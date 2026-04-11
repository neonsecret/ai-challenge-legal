"""Unit tests for _build_drafting_section in arlc/agent/prompts.py.

Covers:
- FIRST-TURN MANDATE present when template selected and no documents exist
- Mandate absent when no template selected (research mode)
- chat_documents section indicates existing documents
"""

from __future__ import annotations

import os

os.environ.setdefault("VERTEX_PROJECT_ID", "test-project")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from arlc.agent.prompts import _build_drafting_section


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
    state = _make_state(template_slug="zaloba-o-nahrade-skody", template_name="Žaloba o náhradě škody")
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
    docs = [{"id": "uuid-abc", "template_slug": "z", "version": 2, "fields": {"claimant": "Jan Novák"}}]
    state = _make_state(template_slug="z", chat_documents=docs)
    section = _build_drafting_section(state)
    assert "uuid-abc" in section
    assert "action=update" in section


def test_no_documents_prompts_action_create():
    state = _make_state(template_slug="z", chat_documents=[])
    section = _build_drafting_section(state)
    assert "action=create" in section
    assert "No documents exist" in section
