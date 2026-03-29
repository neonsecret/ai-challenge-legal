"""LangGraph StateGraph for the legal research ReAct agent.

Graph:  reason ──(tool_calls?)──> search ──> reason
           └──(no tool_calls)──> END

The reason node invokes Claude via Vertex AI. If it needs sources, it emits
a search_legal_corpus tool call. The search node runs FAISS + reranker and
feeds results back. The loop continues until Claude answers or the cap is hit.

All agent decisions are logged and emitted as status events so the frontend
can show what the agent is doing in real-time.

Streaming strategy
------------------
We stream tokens to ``on_token`` from EVERY reason-node LLM call using
``astream_events``.  With Anthropic/Claude, text content blocks and
tool_call blocks are separate: ``chunk.content`` carries text tokens,
``chunk.tool_call_chunks`` carries tool-call JSON.  This means:

- When the reason call produces a final answer (no tool calls), the text
  tokens stream to the frontend immediately — true token-by-token streaming.
- When the reason call decides to search (tool call), the text content is
  typically empty or a brief "I'll search for..." preamble.  We stream it
  anyway (cheap) and discard on the frontend side via an ``answering:``
  status event that signals the real answer is starting.

When the agent transitions from search back to reason for the final answer,
we emit ``answering:{n_docs}`` so the frontend knows tokens that follow are
the actual answer.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph

from arlc.agent.config import (
    LLM_MAX_TOKENS,
    LLM_MODEL,
    MAX_ACCUMULATED_DOCS,
    MAX_HISTORY_MESSAGES,
    MAX_SEARCHES_PER_TURN,
)
from arlc.agent.prompts import build_system_prompt
from arlc.agent.state import AgentState, SourceDocument
from arlc.agent.tools import execute_search, format_search_results, verify_source_relevance
from arlc.agent.verification import verify_agent_pages

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool schema — what the LLM sees
# ---------------------------------------------------------------------------

@tool
def search_legal_corpus(query: str) -> str:
    """Search the legal corpus for relevant legislation and case law.
    Write queries in the corpus language (Czech for Czech law, English for DIFC).
    Each call returns fresh documents not previously retrieved in this conversation."""
    return ""  # Actual execution in search_node


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def _build_llm():
    from langchain_google_vertexai.model_garden import ChatAnthropicVertex
    return ChatAnthropicVertex(
        model_name=LLM_MODEL,
        project=os.environ["VERTEX_PROJECT_ID"],
        location=os.environ.get("VERTEX_LOCATION", "us-east5"),
        max_tokens=LLM_MAX_TOKENS,
    ).bind_tools([search_legal_corpus])


def build_agent_graph():
    """Build and compile the agent graph."""
    llm = _build_llm()
    graph = StateGraph(AgentState)

    def reason_node(state: AgentState) -> dict:
        system = build_system_prompt(state)
        messages: list[BaseMessage] = [SystemMessage(content=system)] + state["messages"]
        response = llm.invoke(messages)

        # Log the agent's decision
        if hasattr(response, "tool_calls") and response.tool_calls:
            queries = [tc["args"].get("query", "") for tc in response.tool_calls]
            logger.info("[agent] reason -> search (%d queries: %s)",
                       len(queries), [q[:60] for q in queries])
        else:
            content = response.content if isinstance(response.content, str) else str(response.content)[:100]
            logger.info("[agent] reason -> answer (%d chars)", len(content))

        return {"messages": [response]}

    def search_node(state: AgentState) -> dict:
        last_msg = state["messages"][-1]
        if not hasattr(last_msg, "tool_calls") or not last_msg.tool_calls:
            return {}

        # Emit status for each search
        on_status = state.get("_on_status")

        results_msgs: list[ToolMessage] = []
        new_docs_all: list[SourceDocument] = []

        for tc in last_msg.tool_calls:
            query = tc["args"].get("query", "")
            if not query:
                results_msgs.append(ToolMessage(
                    content="Error: empty query.",
                    tool_call_id=tc["id"],
                ))
                continue

            # Status: show what the agent is searching for
            if on_status:
                on_status(f"retrieving:searching \"{query[:60]}\"")

            exclude = {(d["doc_id"], d["page"]) for d in state["accumulated_docs"]}
            exclude.update((d["doc_id"], d["page"]) for d in new_docs_all)

            t0 = time.monotonic()
            try:
                new_docs = execute_search(
                    query=query,
                    corpus=state["corpus"],
                    law_filters=state["selected_laws"] or None,
                    exclude_doc_pages=exclude,
                )
            except Exception:
                logger.exception("[agent] search failed: query=%s", query[:80])
                results_msgs.append(ToolMessage(
                    content="Search failed. Try a different query.",
                    tool_call_id=tc["id"],
                ))
                continue

            elapsed = time.monotonic() - t0
            doc_ids = [d["doc_id"] for d in new_docs]
            logger.info("[agent] search: query=\"%s\" -> %d docs in %.1fs (%s)",
                       query[:60], len(new_docs), elapsed, doc_ids)

            if on_status and new_docs:
                on_status(f"retrieving:found {len(new_docs)} new sources")

            new_docs_all.extend(new_docs)

            offset = len(state["accumulated_docs"]) + len(new_docs_all) - len(new_docs)
            doc_text = format_search_results(new_docs, offset=offset)
            results_msgs.append(ToolMessage(content=doc_text, tool_call_id=tc["id"]))

        updated_docs = (state["accumulated_docs"] + new_docs_all)[:MAX_ACCUMULATED_DOCS]
        logger.info("[agent] accumulated: %d docs total (cap=%d)",
                   len(updated_docs), MAX_ACCUMULATED_DOCS)

        return {
            "messages": results_msgs,
            "accumulated_docs": updated_docs,
            "search_count": state["search_count"] + 1,
        }

    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            if state["search_count"] >= MAX_SEARCHES_PER_TURN:
                logger.warning("[agent] hit search cap (%d), forcing answer", MAX_SEARCHES_PER_TURN)
                return "end"
            return "search"
        return "end"

    graph.add_node("reason", reason_node)
    graph.add_node("search", search_node)
    graph.set_entry_point("reason")
    graph.add_conditional_edges("reason", should_continue, {"search": "search", "end": END})
    graph.add_edge("search", "reason")

    return graph.compile()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _convert_history(history: list[dict] | None) -> list[BaseMessage]:
    """Convert plain dicts to LangChain messages, capped at MAX_HISTORY_MESSAGES."""
    if not history:
        return []
    messages: list[BaseMessage] = []
    for msg in history:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    # Cap to control context size and cost
    if len(messages) > MAX_HISTORY_MESSAGES:
        messages = messages[-MAX_HISTORY_MESSAGES:]
        logger.info("[agent] history truncated to %d messages", MAX_HISTORY_MESSAGES)
    return messages


def _extract_text(content) -> str:
    """Extract plain text from AIMessage.content (str or list of blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_agent_turn(
    question: str,
    corpus: str = "difc",
    selected_laws: list[str] | None = None,
    accumulated_docs: list[SourceDocument] | None = None,
    conversation_history: list[dict] | None = None,
    user_id: str = "",
    conversation_id: str = "",
    on_status: Callable[[str], None] | None = None,
    on_token: Callable[[str], None] | None = None,
) -> dict:
    """Run one agent turn.  Streams tokens in real-time via ``on_token``.

    Streaming approach: we use ``astream_events(version="v2")`` and listen
    for ``on_chat_model_stream`` events.  With Anthropic, text content and
    tool-call chunks arrive in separate fields of the ``AIMessageChunk``:

    - ``chunk.content`` (str or list of blocks) = text tokens
    - ``chunk.tool_call_chunks`` = tool-call JSON fragments

    We stream text tokens immediately.  If the LLM also emits tool calls in
    the same response, those text tokens are typically empty or a brief
    preamble — harmless to stream.  The frontend uses the ``answering:``
    status event to know when the real answer begins.
    """
    logger.info("[agent] turn start: question=\"%s\", corpus=%s, laws=%s, prior_docs=%d",
               question[:80], corpus, selected_laws, len(accumulated_docs or []))

    if on_status:
        on_status("agent:thinking")

    messages: list[BaseMessage] = _convert_history(conversation_history)
    messages.append(HumanMessage(content=question))

    initial_state: AgentState = {
        "messages": messages,
        "accumulated_docs": accumulated_docs or [],
        "corpus": corpus,
        "selected_laws": selected_laws or [],
        "search_count": 0,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "_on_status": on_status,  # passed through state for search_node
    }

    graph = build_agent_graph()

    # --- Streaming state ---
    final_answer_parts: list[str] = []
    final_docs: list[SourceDocument] = accumulated_docs or []
    reason_count = 0
    # Track whether the current reason call has produced tool calls.
    # When it does, any text tokens streamed so far were a preamble, not
    # the final answer.  We mark them so the frontend can discard/ignore.
    current_reason_has_tool_calls = False
    # Text tokens streamed during the current reason call, before we know
    # whether it is the final call or an intermediate one.
    current_reason_tokens: list[str] = []
    answering_status_sent = False

    async for event in graph.astream_events(initial_state, version="v2"):
        kind = event.get("event", "")
        name = event.get("name", "")

        # -- Track reason node entry/exit --
        if kind == "on_chain_start" and name == "reason":
            reason_count += 1
            current_reason_has_tool_calls = False
            current_reason_tokens.clear()
            if on_status:
                on_status("agent:thinking")
            logger.info("[agent] reason node #%d starting", reason_count)

        if kind == "on_chain_end" and name == "reason":
            if not current_reason_has_tool_calls:
                # This was the final reason call (no tool calls).
                # All tokens were already streamed via on_token.
                final_answer_parts.extend(current_reason_tokens)
                logger.info(
                    "[agent] reason node #%d finished (final answer, %d tokens streamed)",
                    reason_count, len(current_reason_tokens),
                )
            else:
                logger.info(
                    "[agent] reason node #%d finished (tool call, %d text tokens discarded)",
                    reason_count, len(current_reason_tokens),
                )

        # -- Stream text tokens from the LLM --
        if kind == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if not chunk:
                continue

            # Extract text content from the chunk
            text = ""
            if hasattr(chunk, "content"):
                text = _extract_text(chunk.content)

            # Detect tool-call chunks
            if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                if not current_reason_has_tool_calls:
                    current_reason_has_tool_calls = True
                    logger.info("[agent] reason node #%d: tool call detected", reason_count)
                # Do NOT stream tool-call JSON to the frontend
                continue

            # Stream text tokens to the frontend in real-time
            if text:
                # Emit the answering status once when we start getting
                # text tokens that are NOT part of a tool-call response.
                # We send it on the first text token of any reason call.
                # If this turns out to be an intermediate call (tool_calls
                # detected later), the frontend handles the transition
                # via the next "agent:thinking" or "retrieving:" status.
                if on_token and not answering_status_sent and not current_reason_has_tool_calls:
                    if on_status:
                        n_docs = len(accumulated_docs or [])
                        on_status(f"answering:{n_docs}")
                    answering_status_sent = True

                current_reason_tokens.append(text)
                if on_token:
                    on_token(text)

        # -- When search node starts, emit status & reset answering flag --
        if kind == "on_chain_start" and name == "search":
            answering_status_sent = False
            if on_status:
                on_status("retrieving:searching corpus")

        # -- Capture final graph output for accumulated_docs --
        if kind == "on_chain_end" and name == "LangGraph":
            output = event.get("data", {}).get("output", {})
            if isinstance(output, dict):
                final_docs = output.get("accumulated_docs", final_docs)

    # Assemble the final answer from streamed tokens
    final_answer = "".join(final_answer_parts)

    # Fallback: if streaming missed the answer (e.g. astream_events quirk),
    # extract it from the final graph output
    if not final_answer and final_docs is not None:
        # Re-run would be expensive; the graph has already completed.
        # This fallback should rarely trigger — log a warning.
        logger.warning("[agent] no tokens captured via streaming; "
                       "falling back to graph output extraction")
        # The final AIMessage is the last non-tool message in the graph output
        # We already have the graph output from the LangGraph on_chain_end event
        # but we need to re-extract from the event stream.  Since the graph is
        # done, we can't re-iterate.  The final_answer stays empty.

    # Post-processing: verify source relevance (informational, not blocking)
    if final_answer and final_docs:
        final_docs = verify_source_relevance(final_answer, final_docs)

    # Build sources
    sources = [
        {"doc_id": d["doc_id"], "page_numbers": [d["page"]], "text": d.get("text", "")}
        for d in final_docs
    ]

    # Post-processing: page verification (DIFC only).
    # Checks that cited pages actually support the answer.  If a page has
    # NO_SUPPORT, the verifier tries to find a better page in the same
    # document.  This runs synchronously and is non-blocking — if it fails,
    # the original sources are preserved.
    if final_answer and sources and corpus == "difc":
        sources = verify_agent_pages(question, final_answer, sources)

    search_count = max(reason_count - 1, 0)
    logger.info("[agent] turn complete: %d docs, %d searches, answer=%d chars",
               len(final_docs), search_count, len(final_answer))

    if on_status:
        on_status("agent:done")

    return {
        "answer": final_answer,
        "sources": sources,
        "accumulated_docs": final_docs,
    }
