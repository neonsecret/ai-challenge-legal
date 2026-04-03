"""Unit tests for the module-level graph node functions extracted from build_agent_graph.

Covers:
- cap_reached_node: produces one ToolMessage per tool call, increments search_count
- should_continue: routing logic for end / search / cap_reached branches
"""

from __future__ import annotations

import os

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

# Provide required env vars before importing the module so config doesn't fail.
os.environ.setdefault("VERTEX_PROJECT_ID", "test-project")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from arlc.agent.config import MAX_SEARCHES_PER_TURN
from arlc.agent.graph import _CASELAW_TOOLS, cap_reached_node, should_continue

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ai_tool_calls(*tool_names: str) -> AIMessage:
    """Return an AIMessage whose tool_calls list has one entry per name."""
    return AIMessage(
        content="",
        tool_calls=[
            {"id": f"tc_{i}", "name": name, "args": {"query": "test"}, "type": "tool_call"}
            for i, name in enumerate(tool_names)
        ],
    )


def _base_state(
    search_count: int = 0,
    extra_messages: list | None = None,
) -> dict:
    """Minimal AgentState-compatible dict for node testing."""
    messages = [HumanMessage(content="What does Article 5 say?")]
    if extra_messages:
        messages.extend(extra_messages)
    return {
        "messages": messages,
        "accumulated_docs": [],
        "corpus": "difc",
        "selected_laws": [],
        "search_count": search_count,
        "user_id": "u-test",
        "conversation_id": "c-test",
    }


# ---------------------------------------------------------------------------
# cap_reached_node
# ---------------------------------------------------------------------------


class TestCapReachedNode:
    def test_single_tool_call_returns_one_tool_message(self):
        ai_msg = _make_ai_tool_calls("search_legal_corpus")
        state = _base_state(search_count=3, extra_messages=[ai_msg])
        result = cap_reached_node(state)

        assert len(result["messages"]) == 1
        msg = result["messages"][0]
        assert isinstance(msg, ToolMessage)
        assert msg.tool_call_id == "tc_0"
        assert "Search limit reached" in msg.content

    def test_multiple_tool_calls_produce_one_message_each(self):
        ai_msg = _make_ai_tool_calls("search_legal_corpus", "search_court_decisions", "fetch_court_decision")
        state = _base_state(search_count=2, extra_messages=[ai_msg])
        result = cap_reached_node(state)

        assert len(result["messages"]) == 3
        ids = {m.tool_call_id for m in result["messages"]}
        assert ids == {"tc_0", "tc_1", "tc_2"}

    def test_search_count_incremented_by_number_of_tool_calls(self):
        ai_msg = _make_ai_tool_calls("search_legal_corpus", "search_legal_corpus")
        state = _base_state(search_count=4, extra_messages=[ai_msg])
        result = cap_reached_node(state)

        assert result["search_count"] == 6  # 4 + 2 tool calls

    def test_tool_message_content_tells_llm_to_answer(self):
        ai_msg = _make_ai_tool_calls("search_legal_corpus")
        state = _base_state(search_count=0, extra_messages=[ai_msg])
        result = cap_reached_node(state)

        msg = result["messages"][0]
        assert "Do NOT call any more tools" in msg.content
        assert "documents already retrieved" in msg.content


# ---------------------------------------------------------------------------
# should_continue
# ---------------------------------------------------------------------------


class TestShouldContinue:
    def test_no_tool_calls_returns_end(self):
        ai_msg = AIMessage(content="Here is your answer.")
        state = _base_state(search_count=0, extra_messages=[ai_msg])
        assert should_continue(state) == "end"

    def test_tool_call_below_cap_returns_search(self):
        ai_msg = _make_ai_tool_calls("search_legal_corpus")
        state = _base_state(search_count=0, extra_messages=[ai_msg])
        assert should_continue(state) == "search"

    def test_corpus_tool_at_cap_returns_cap_reached(self):
        ai_msg = _make_ai_tool_calls("search_legal_corpus")
        state = _base_state(search_count=MAX_SEARCHES_PER_TURN, extra_messages=[ai_msg])
        assert should_continue(state) == "cap_reached"

    def test_corpus_tool_one_below_cap_returns_search(self):
        ai_msg = _make_ai_tool_calls("search_legal_corpus")
        state = _base_state(search_count=MAX_SEARCHES_PER_TURN - 1, extra_messages=[ai_msg])
        assert should_continue(state) == "search"

    def test_caselaw_only_below_budget_returns_search(self):
        # Build history with 9 caselaw tool calls already made
        prior_calls = [_make_ai_tool_calls("search_court_decisions") for _ in range(9)]
        ai_msg = _make_ai_tool_calls("search_court_decisions")
        state = _base_state(search_count=0, extra_messages=prior_calls + [ai_msg])
        # 9 prior + 1 current = 10 → should trip the cap
        assert should_continue(state) == "cap_reached"

    def test_caselaw_only_nine_calls_returns_search(self):
        # 8 prior caselaw calls → current would be the 9th → still under 10
        prior_calls = [_make_ai_tool_calls("search_court_decisions") for _ in range(8)]
        ai_msg = _make_ai_tool_calls("search_court_decisions")
        state = _base_state(search_count=0, extra_messages=prior_calls + [ai_msg])
        assert should_continue(state) == "search"

    def test_mixed_tools_counted_against_corpus_cap(self):
        """If the last message has both corpus and caselaw tools, corpus cap applies."""
        ai_msg = _make_ai_tool_calls("search_legal_corpus", "search_court_decisions")
        state = _base_state(search_count=MAX_SEARCHES_PER_TURN, extra_messages=[ai_msg])
        assert should_continue(state) == "cap_reached"

    def test_caselaw_tools_constant_contains_expected_names(self):
        assert "search_court_decisions" in _CASELAW_TOOLS
        assert "fetch_court_decision" in _CASELAW_TOOLS
        assert "search_legal_corpus" not in _CASELAW_TOOLS
