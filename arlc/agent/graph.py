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

import asyncio
import logging
import os
import re
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
    LLM_MODEL_FAST,
    MAX_ACCUMULATED_DOCS,
    MAX_HISTORY_MESSAGES,
    MAX_SEARCHES_PER_TURN,
    MAX_WEB_SOURCES,
    WEB_SEARCH_ENABLED,
)
from arlc.agent.prompts import build_document_context, build_system_prompt
from arlc.agent.state import AgentState, SourceDocument
from arlc.agent.tools import (
    execute_search,
    execute_web_search,
    format_search_results,
    format_web_results,
    verify_source_relevance,
)
from arlc.agent.verification import verify_agent_pages

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool schema — what the LLM sees
# ---------------------------------------------------------------------------


@tool
def search_legal_corpus(query: str) -> str:
    """Search the legal corpus for relevant legislation, regulations, and case law.

    Call this tool whenever you need source documents to ground a legal claim, find
    a specific article or provision, or retrieve case outcomes. Write queries in the
    corpus language (Czech for Czech law, English for DIFC/UK/AU). Use precise legal
    terminology — include article numbers, law names, or case identifiers when known.
    Returns document chunks labelled [DOC-N] with the document ID and page number.
    Each call returns only documents not yet retrieved in this conversation.
    Do NOT call for greetings, general chitchat, or questions unrelated to law."""
    raise RuntimeError("search_legal_corpus is schema-only; execution handled by search_node")


@tool
def search_court_decisions(
    query: str,
    statute_reference: str = "",
    date_from: str = "",
    date_to: str = "",
) -> str:
    """Search Czech Supreme Court case law (judikatura) to find how courts have
    interpreted and applied the law in specific cases. Returns case summaries
    with the legal principle (pravni veta) established by each decision.

    Use this when you need to understand judicial interpretation, court practice,
    legal precedent, or how a statutory provision has been applied in real cases.

    Write search queries in Czech. Always search statutory law first to identify
    the relevant provision, then search case law to see how courts interpreted it.

    Parameters:
    - query: search terms in Czech
    - statute_reference: optional statute filter — use "law_number/law_year" for
      all decisions citing a statute (e.g. "262/2006" for Labour Code), or
      "law_number/law_year § paragraph" for decisions citing a specific paragraph
      (e.g. "89/2012 § 2079" for NOZ § 2079, "262/2006 § 52" for ZP § 52).
      ALWAYS include the paragraph when the user asks about a specific provision.
    - date_from: optional start date in ISO format "YYYY-MM-DD"
    - date_to: optional end date in ISO format "YYYY-MM-DD"
    """
    raise RuntimeError("search_court_decisions is schema-only; execution handled by search_node")


@tool
def fetch_court_decision(ecli: str) -> str:
    """Retrieve the full reasoning text of a specific Czech court decision to
    read the court's detailed legal analysis. Use this after
    search_court_decisions has returned summaries — select the most relevant
    case(s) and fetch their full text to cite specific passages in your answer.

    Pass the ECLI identifier from the search results (e.g.
    "ECLI:CZ:NS:2023:21.CDO.1234.2023.1").
    """
    raise RuntimeError("fetch_court_decision is schema-only; execution handled by search_node")


@tool
def search_web(query: str) -> str:
    """Search the internet for current legal information not available in the corpus.

    Use ONLY when: (1) corpus search returned insufficient results AND (2) the question
    requires up-to-date figures such as minimum wage amounts, interest rates, fee schedules,
    or recent legislative amendments. Always try corpus search first. Returns snippets with
    URLs labelled [WEB: "Title"](URL) — treat as unverified. Prefer corpus sources for
    legal interpretation; web sources only for current numerical values the corpus references
    but does not specify."""
    raise RuntimeError("search_web is schema-only; execution handled by search_node")


# ---------------------------------------------------------------------------
# Czech statute extraction for auto-enrichment
# ---------------------------------------------------------------------------

# Map Czech statute doc_id prefixes to human-readable Czech statute names.
# These names appear in court decision tsvectors (e.g., "zákoník" and "práce"
# are separate tokens that help BM25 find decisions discussing this statute).
_CZECH_STATUTE_NAMES: dict[str, str] = {
    "zakonik_prace": "zákoník práce",
    "obcansky_zakonik": "občanský zákoník",
    "zakon_obch_korporace": "obchodní korporace",
    "trestni_zakonik": "trestní zákoník",
    "danovy_rad": "daňový řád",
    "zakon_dane_prijmu": "daň příjmů",
    "zakon_dph": "daň přidané hodnoty",
    "zakon_duchodove_pojisteni": "důchodové pojištění",
    "zakon_nemocenske_pojisteni": "nemocenské pojištění",
    "spravni_rad": "správní řád",
    "zivnostensky_zakon": "živnostenský zákon",
}

# Common Czech legal boilerplate words to exclude from extracted terms
_BOILERPLATE_TERMS = frozenset(
    {
        "ustanovení",
        "odstavec",
        "odstavce",
        "písmeno",
        "případě",
        "přičemž",
        "zejména",
        "uvedené",
        "uvedených",
        "následující",
        "předchozí",
        "podmínek",
        "podmínky",
        "stanoví",
        "příslušný",
        "příslušné",
        "příslušných",
        "smluvní",
        "právních",
        "právního",
        "způsobem",
        "přiměřeně",
        "nejpozději",
        "nejméně",
        "nejvýše",
        "alespoň",
        "povinen",
        "povinnost",
        "povinnosti",
        "oprávněn",
        "oprávnění",
        "rozhodnutí",
        "skutečnosti",
        "skutečnost",
        "příslušného",
        # Common party/entity words — too generic for case law search
        "zaměstnavatel",
        "zaměstnavatele",
        "zaměstnavateli",
        "zaměstnavatelé",
        "zaměstnanec",
        "zaměstnance",
        "zaměstnanci",
        "zaměstnanců",
        "společnost",
        "společnosti",
        "účastník",
        "účastníků",
        "účastníci",
        "smlouvy",
        "smlouva",
        "smlouvou",
        "dohody",
        "dohoda",
        "dohodou",
    }
)


def _extract_caselaw_query(docs: list[SourceDocument]) -> str:
    """Build a focused BM25 query for case law from statute search results.

    Extracts the first § section number + 1-2 key substantive legal terms
    from the statute text. Keeps the query SHORT to avoid diluting the OR
    search — with prefix matching, fewer focused terms beat many broad ones.

    Example: statute text about "§ 52 ... nadbytečným ... výpověď" produces
    query ``"52 nadbytečným výpověď"`` which, via prefix BM25, matches
    decisions containing "nadbytečným", "nadbytečnost", "výpovědi", etc.

    Parameters
    ----------
    docs : list[SourceDocument]
        Statute search results from execute_search().

    Returns
    -------
    str
        Focused BM25 query string, or empty string if nothing extracted.
    """
    first_section = ""
    statute_name = ""
    key_terms: list[str] = []
    _seen: set[str] = set()

    for doc in docs:
        doc_id = doc.get("doc_id", "")
        doc_text = doc.get("text", "")

        # Get statute name from doc_id
        if not statute_name:
            base_id = re.sub(r"_\d+$", "", doc_id)
            statute_name = _CZECH_STATUTE_NAMES.get(base_id, "")

        # Get first § section number only
        if not first_section:
            m = re.search(r"§\s*(\d+)", doc_text)
            if m:
                first_section = m.group(1)

        # Extract substantive legal terms (7+ chars, not boilerplate)
        for m in re.finditer(r"[a-záčďéěíňóřšťúůýž]{7,}", doc_text.lower()):
            term = m.group(0)
            if term not in _seen and term not in _BOILERPLATE_TERMS and len(key_terms) < 2:
                _seen.add(term)
                key_terms.append(term)

    # Build focused query: section number + key terms (max 3-4 tokens total)
    parts: list[str] = []
    if first_section:
        parts.append(first_section)
    parts.extend(key_terms)
    # Add statute name last (lower priority — helps but not essential)
    if statute_name and len(parts) < 4:
        parts.append(statute_name)

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

# Tool names that belong to the case-law budget (not the corpus search cap).
_CASELAW_TOOLS: frozenset[str] = frozenset({"search_court_decisions", "fetch_court_decision"})


def should_continue(state: AgentState) -> str:
    """Route the graph after a reason-node invocation.

    Returns
    -------
    "search"
        There are pending tool calls and the relevant budget has not been hit.
    "cap_reached"
        A tool-call budget (corpus or case-law) has been exhausted.
    "end"
        The LLM produced a final answer (no tool calls).
    """
    last = state["messages"][-1]
    if not (hasattr(last, "tool_calls") and last.tool_calls):
        return "end"

    has_only_caselaw = all(tc["name"] in _CASELAW_TOOLS for tc in last.tool_calls)
    if has_only_caselaw:
        # Case-law tools have a separate budget (10 calls max).
        caselaw_count = sum(
            1
            for m in state["messages"]
            if hasattr(m, "tool_calls")
            for tc in (m.tool_calls or [])
            if tc.get("name") in _CASELAW_TOOLS
        )
        if caselaw_count >= 10:
            logger.warning("[agent] hit caselaw cap (10), forcing answer")
            return "cap_reached"
        return "search"

    if state["search_count"] >= MAX_SEARCHES_PER_TURN:
        logger.warning("[agent] hit search cap (%d), forcing answer", MAX_SEARCHES_PER_TURN)
        return "cap_reached"
    return "search"


def cap_reached_node(state: AgentState) -> dict:
    """When search cap is hit, respond to pending tool calls telling the LLM to answer.

    Increments search_count to prevent infinite loops: if the LLM ignores
    the instruction and issues tool calls again, should_continue routes here
    again but search_count keeps rising. After MAX_SEARCHES_PER_TURN + 3
    cap_reached iterations, the agent timeout (600s) will terminate it.

    Parameters
    ----------
    state : AgentState
        Current graph state. ``state["messages"][-1]`` must be an AIMessage
        with at least one tool call.

    Returns
    -------
    dict
        State delta: ``messages`` (ToolMessage replies) and incremented
        ``search_count``.
    """
    last_msg = state["messages"][-1]
    results = [
        ToolMessage(
            content="Search limit reached. You MUST answer now using the documents already retrieved. Do NOT call any more tools.",
            tool_call_id=tc["id"],
        )
        for tc in last_msg.tool_calls
    ]
    return {
        "messages": results,
        "search_count": state["search_count"] + len(last_msg.tool_calls),
    }


def _build_llm_pair():
    """Build fast (Haiku) and full (Sonnet) LLMs for two-round strategy.

    The first reason call only decides "I need to search" and writes a query —
    perfect for Haiku (cheap, fast).  Subsequent calls generate the grounded
    answer and need Sonnet.
    """
    from langchain_google_vertexai.model_garden import ChatAnthropicVertex

    base_kwargs = dict(
        project=os.environ["VERTEX_PROJECT_ID"],
        location=os.environ.get("VERTEX_LOCATION", "us-east5"),
    )

    tools = [search_legal_corpus, search_court_decisions, fetch_court_decision]
    if WEB_SEARCH_ENABLED:
        tools.append(search_web)
        logger.info("[agent] web search tool enabled")

    fast = ChatAnthropicVertex(
        model_name=LLM_MODEL_FAST,
        max_tokens=1024,  # First round only needs short tool calls
        **base_kwargs,
    ).bind_tools(tools)

    full = ChatAnthropicVertex(
        model_name=LLM_MODEL,
        max_tokens=LLM_MAX_TOKENS,
        **base_kwargs,
    ).bind_tools(tools)

    return fast, full


_compiled_graph = None


def _get_agent_graph():
    """Return the cached compiled agent graph (singleton).

    The graph is stateless — per-request data (``on_status``, docs, messages)
    flows through the ``AgentState`` dict, so a single compiled graph is safe
    to reuse across requests.  This avoids re-building the LLM bindings and
    compiling the StateGraph on every turn.
    """
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_agent_graph()
    return _compiled_graph


def build_agent_graph():
    """Build and compile the agent graph."""
    fast_llm, full_llm = _build_llm_pair()
    graph = StateGraph(AgentState)

    def reason_node(state: AgentState) -> dict:
        # First reason call (no AI messages yet) -> use fast Haiku
        has_prior_ai = any(isinstance(m, AIMessage) for m in state["messages"])
        llm = full_llm if has_prior_ai else fast_llm

        system = build_system_prompt(state)

        # Inject accumulated document context before the user's question.
        # Documents precede instructions per Anthropic long-context guidance
        # (+30% document attention). The system prompt stays fully cacheable
        # because it no longer contains the dynamic document section.
        doc_section = build_document_context(state)
        state_messages = list(state["messages"])
        if doc_section:
            # Scan in REVERSE to find the LAST HumanMessage (current question),
            # not the first one (which may be historical in multi-turn sessions).
            for i in range(len(state_messages) - 1, -1, -1):
                if isinstance(state_messages[i], HumanMessage):
                    state_messages[i] = HumanMessage(content=f"{doc_section}\n\n---\n\n{state_messages[i].content}")
                    break

        messages: list[BaseMessage] = [SystemMessage(content=system)] + state_messages
        response = llm.invoke(messages)

        # Log the agent's decision including which model was used
        model_name = LLM_MODEL if has_prior_ai else LLM_MODEL_FAST
        if hasattr(response, "tool_calls") and response.tool_calls:
            queries = [tc["args"].get("query", "") for tc in response.tool_calls]
            logger.info(
                "[agent] reason -> search [%s] (%d queries: %s)",
                model_name.split("-")[1],
                len(queries),
                [q[:60] for q in queries],
            )
        else:
            content = response.content if isinstance(response.content, str) else str(response.content)[:100]
            logger.info("[agent] reason -> answer [%s] (%d chars)", model_name.split("-")[1], len(content))

        return {"messages": [response]}

    async def search_node(state: AgentState) -> dict:
        last_msg = state["messages"][-1]
        if not hasattr(last_msg, "tool_calls") or not last_msg.tool_calls:
            return {}

        # Emit status for each search
        on_status = state.get("_on_status")

        results_msgs: list[ToolMessage] = []
        new_docs_all: list[SourceDocument] = []
        new_web_sources: list[dict] = []
        # Czech auto-enrichment: fire once per turn so the agent sees case law
        # alongside the first statute result without having to decide to search.
        _caselaw_auto_triggered = False

        for tc in last_msg.tool_calls:
            query = tc["args"].get("query", "")
            if not query:
                results_msgs.append(
                    ToolMessage(
                        content="Error: empty query.",
                        tool_call_id=tc["id"],
                    ),
                )
                continue

            # --- Case law search tool ---
            if tc["name"] == "search_court_decisions":
                if on_status:
                    on_status("retrieving:searching case law")
                from arlc.agent.caselaw_tools import (
                    execute_caselaw_search,
                    format_caselaw_search_results,
                )

                try:
                    caselaw_docs = await execute_caselaw_search(
                        query=query,
                        statute_reference=tc["args"].get("statute_reference", ""),
                        date_from=tc["args"].get("date_from", ""),
                        date_to=tc["args"].get("date_to", ""),
                    )
                except Exception:
                    logger.exception("[agent] caselaw search failed: query=%s", query[:80])
                    results_msgs.append(
                        ToolMessage(
                            content="Case law search failed. Try a different query.",
                            tool_call_id=tc["id"],
                        ),
                    )
                    continue

                content = format_caselaw_search_results(caselaw_docs)
                if on_status and caselaw_docs:
                    on_status(f"retrieving:found {len(caselaw_docs)} case law results")
                logger.info(
                    '[agent] caselaw search: query="%s" → %d results',
                    query[:60],
                    len(caselaw_docs),
                )

                # Auto-promote: fetch top results with legal theses and inject
                # as [DOC-N] sources so the agent can cite them without a
                # separate fetch_court_decision call.
                from arlc.agent.caselaw_tools import (
                    execute_caselaw_fetch,
                    format_caselaw_full,
                )

                # Deduplicate: skip ECLIs already in accumulated or new docs
                seen_eclis = {d.get("ecli", d["doc_id"]) for d in state["accumulated_docs"]}
                seen_eclis.update(d.get("ecli", d["doc_id"]) for d in new_docs_all)

                promoted_parts: list[str] = []
                promoted_count = 0
                for cd in caselaw_docs:
                    if promoted_count >= 3:
                        break
                    ecli = cd.get("ecli", "")
                    if not ecli or not cd.get("legal_thesis") or ecli in seen_eclis:
                        continue
                    try:
                        full_doc = await execute_caselaw_fetch(ecli)
                    except Exception:  # nosec B112 — caselaw fetch errors are non-fatal
                        continue
                    if full_doc:
                        doc_idx = len(state["accumulated_docs"]) + len(new_docs_all) + 1
                        new_docs_all.append(full_doc)
                        seen_eclis.add(ecli)
                        promoted_parts.append(format_caselaw_full(full_doc, doc_idx))
                        promoted_count += 1

                if promoted_parts:
                    content = content + "\n---\n" + "\n---\n".join(promoted_parts)
                    logger.info(
                        "[agent] caselaw auto-promote: %d decisions promoted to [DOC-N]",
                        promoted_count,
                    )

                results_msgs.append(ToolMessage(content=content, tool_call_id=tc["id"]))
                continue

            # --- Case law fetch tool ---
            if tc["name"] == "fetch_court_decision":
                ecli = tc["args"].get("ecli", "")
                if not ecli:
                    results_msgs.append(
                        ToolMessage(
                            content="Error: ecli argument is required.",
                            tool_call_id=tc["id"],
                        ),
                    )
                    continue

                if on_status:
                    on_status("retrieving:fetching court decision")
                from arlc.agent.caselaw_tools import execute_caselaw_fetch, format_caselaw_full

                try:
                    fetched_doc = await execute_caselaw_fetch(ecli)
                except Exception:
                    logger.exception("[agent] caselaw fetch failed: ecli=%s", ecli)
                    results_msgs.append(
                        ToolMessage(
                            content=f"Failed to fetch decision {ecli}. Try searching for it instead.",
                            tool_call_id=tc["id"],
                        ),
                    )
                    continue

                if fetched_doc is None:
                    results_msgs.append(
                        ToolMessage(
                            content=f"Decision not found: {ecli}",
                            tool_call_id=tc["id"],
                        ),
                    )
                    continue

                # Add to accumulated docs so it gets proper [DOC-N] numbering
                doc_offset = len(state["accumulated_docs"]) + len(new_docs_all) + 1
                content = format_caselaw_full(fetched_doc, doc_offset)
                new_docs_all.append(fetched_doc)
                logger.info("[agent] caselaw fetch: ecli=%s → %d chars", ecli[:60], len(content))
                results_msgs.append(ToolMessage(content=content, tool_call_id=tc["id"]))
                continue

            # --- Web search tool ---
            if tc["name"] == "search_web":
                # Check per-request internet toggle (defaults to True when absent)
                if not state.get("use_internet", True):
                    logger.info('[agent] web search skipped (use_internet=False): query="%s"', query[:60])
                    results_msgs.append(
                        ToolMessage(
                            content="Web search is disabled for this conversation. Use search_legal_corpus instead.",
                            tool_call_id=tc["id"],
                        ),
                    )
                    continue
                if on_status:
                    on_status("retrieving:searching the web")
                web_results = await asyncio.to_thread(execute_web_search, query)
                content = format_web_results(web_results)
                logger.info('[agent] web search: query="%s" -> %d results', query[:60], len(web_results))
                results_msgs.append(ToolMessage(content=content, tool_call_id=tc["id"]))
                # Web results don't go into accumulated_docs (they're not corpus docs)
                # but we track them separately for source citations
                new_web_sources.extend(web_results)
                continue

            # --- Corpus search tool (default) ---
            # Status: user-facing, no internal details
            if on_status:
                on_status("retrieving:searching corpus")

            exclude = {(d["doc_id"], d["page"]) for d in state["accumulated_docs"]}
            exclude.update((d["doc_id"], d["page"]) for d in new_docs_all)

            t0 = time.monotonic()
            try:
                new_docs = await asyncio.to_thread(
                    execute_search,
                    query=query,
                    corpus=state["corpus"],
                    law_filters=state["selected_laws"] or None,
                    exclude_doc_pages=exclude,
                    on_status=on_status,
                    doc_ids=state.get("doc_ids"),
                )
            except Exception:
                logger.exception("[agent] search failed: query=%s", query[:80])
                results_msgs.append(
                    ToolMessage(
                        content="Search failed. Try a different query.",
                        tool_call_id=tc["id"],
                    ),
                )
                continue

            elapsed = time.monotonic() - t0
            doc_ids = [d["doc_id"] for d in new_docs]
            logger.info(
                '[agent] search: query="%s" -> %d docs in %.1fs (%s)',
                query[:60],
                len(new_docs),
                elapsed,
                doc_ids,
            )

            if on_status and new_docs:
                on_status(f"retrieving:found {len(new_docs)} new sources")

            new_docs_all.extend(new_docs)

            offset = len(state["accumulated_docs"]) + len(new_docs_all) - len(new_docs)
            doc_text = format_search_results(new_docs, offset=offset)

            # --- Czech auto-enrichment: inject case law as full [DOC-N] sources ---
            # Fires once per turn when corpus is Czech. Uses statute references
            # extracted from the statute search results (not the raw query) to
            # find court decisions that actually cite the relevant statute sections.
            # Format with format_caselaw_full so the agent sees structured content:
            # type label, legal thesis (authoritative), anotace (supplementary).
            if state["corpus"] == "czech" and not _caselaw_auto_triggered:
                _caselaw_auto_triggered = True
                try:
                    from arlc.agent.caselaw_tools import (
                        execute_caselaw_fetch,
                        execute_caselaw_search,
                        format_caselaw_full,
                    )

                    # Build a focused BM25 query from the statute results:
                    # section number + 1-2 key legal terms. No JSONB statute_ref
                    # filter — nsoud.cz metadata only has procedural codes, not
                    # the substantive statute being interpreted.
                    caselaw_query = _extract_caselaw_query(new_docs) or query
                    logger.info(
                        "[agent] czech auto-enrichment: caselaw_query=%r (original=%r)",
                        caselaw_query,
                        query[:60],
                    )

                    caselaw_summaries = await execute_caselaw_search(
                        caselaw_query,
                        limit=5,
                    )
                    # Auto-fetch full text for top 5 results so agent has citable content
                    # (relevant decisions often rank 3-5 due to common-term pollution)
                    # Deduplicate against already-accumulated docs
                    _seen = {d.get("ecli", d["doc_id"]) for d in state["accumulated_docs"]}
                    _seen.update(d.get("ecli", d["doc_id"]) for d in new_docs_all)
                    caselaw_full_docs = []
                    for summary in caselaw_summaries[:5]:
                        ecli = summary.get("ecli", "")
                        if not ecli or ecli in _seen:
                            continue
                        full_doc = await execute_caselaw_fetch(ecli)
                        if full_doc:
                            caselaw_full_docs.append(full_doc)
                            _seen.add(ecli)

                    if caselaw_full_docs:
                        new_docs_all.extend(caselaw_full_docs)
                        # Format each as structured [DOC-N] with type label,
                        # legal thesis, and full reasoning text
                        case_offset = offset + len(new_docs)
                        case_parts = [
                            format_caselaw_full(cdoc, case_offset + j + 1) for j, cdoc in enumerate(caselaw_full_docs)
                        ]
                        doc_text = doc_text + "\n---\n" + "\n---\n".join(case_parts)
                        logger.info(
                            '[agent] czech auto-enrichment: query="%s" → %d case law docs injected as [DOC-%d]-[DOC-%d]',
                            query[:60],
                            len(caselaw_full_docs),
                            case_offset + 1,
                            case_offset + len(caselaw_full_docs),
                        )
                except Exception:
                    logger.warning("[agent] czech case law auto-enrichment failed", exc_info=True)
                    # Non-fatal: statute results are returned as-is

            results_msgs.append(ToolMessage(content=doc_text, tool_call_id=tc["id"]))

        # Merge new docs with existing, prioritising new over old when at cap.
        # New docs always get included; oldest accumulated docs are evicted if needed.
        combined = state["accumulated_docs"] + new_docs_all
        if len(combined) > MAX_ACCUMULATED_DOCS:
            overflow = len(combined) - MAX_ACCUMULATED_DOCS
            updated_docs = state["accumulated_docs"][overflow:] + new_docs_all
        else:
            updated_docs = combined
        logger.info(
            "[agent] accumulated: %d docs total (cap=%d, new=%d, evicted=%d)",
            len(updated_docs),
            MAX_ACCUMULATED_DOCS,
            len(new_docs_all),
            max(0, len(state["accumulated_docs"]) + len(new_docs_all) - MAX_ACCUMULATED_DOCS),
        )

        # Merge web sources from this search with any from prior iterations, capped
        updated_web_sources = (state.get("web_sources", []) + new_web_sources)[:MAX_WEB_SOURCES]

        # Count actual tool calls dispatched, excluding case law tools (they have a
        # separate DB and should not compete with statute search budget).
        tool_call_count = sum(1 for tc in last_msg.tool_calls if tc["name"] not in _CASELAW_TOOLS)

        return {
            "messages": results_msgs,
            "accumulated_docs": updated_docs,
            "web_sources": updated_web_sources,
            "search_count": state["search_count"] + tool_call_count,
        }

    graph.add_node("reason", reason_node)
    graph.add_node("search", search_node)
    graph.add_node("cap_reached", cap_reached_node)
    graph.set_entry_point("reason")
    graph.add_conditional_edges(
        "reason",
        should_continue,
        {
            "search": "search",
            "cap_reached": "cap_reached",
            "end": END,
        },
    )
    graph.add_edge("search", "reason")
    graph.add_edge("cap_reached", "reason")

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
    use_internet: bool = True,
    doc_ids: list[str] | None = None,
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
    logger.info(
        '[agent] turn start: question="%s", corpus=%s, laws=%s, prior_docs=%d',
        question[:80],
        corpus,
        selected_laws,
        len(accumulated_docs or []),
    )

    if on_status:
        on_status("agent:thinking")

    messages: list[BaseMessage] = _convert_history(conversation_history)
    messages.append(HumanMessage(content=question))

    initial_state: AgentState = {
        "messages": messages,
        "accumulated_docs": accumulated_docs or [],
        "web_sources": [],
        "corpus": corpus,
        "selected_laws": selected_laws or [],
        "search_count": 0,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "use_internet": use_internet,
        "doc_ids": doc_ids,
        "_on_status": on_status,  # passed through state for search_node
    }

    graph = _get_agent_graph()

    # --- Streaming state ---
    final_answer_parts: list[str] = []
    final_docs: list[SourceDocument] = accumulated_docs or []
    final_web_sources: list[dict] = []
    final_search_count = 0
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
                    reason_count,
                    len(current_reason_tokens),
                )
            else:
                logger.info(
                    "[agent] reason node #%d finished (tool call, %d text tokens discarded)",
                    reason_count,
                    len(current_reason_tokens),
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
                final_web_sources = output.get("web_sources", final_web_sources)
                final_search_count = output.get("search_count", 0)

    # Assemble the final answer from streamed tokens
    final_answer = "".join(final_answer_parts)

    # Strip agent preamble — intermediate "thinking" text that leaks through
    # when the agent's final reason call starts with meta-commentary before
    # the actual legal analysis (e.g., "Mám dostatečné podklady...")
    import re as _re

    _preamble_pat = _re.compile(
        r"^(?:(?:Hledám|Prohledávám|Vyhledám|Mám dostat|Výsledky|Nyní|Na základě)[^\n]*\n*)+",
    )
    final_answer = _preamble_pat.sub("", final_answer).lstrip("\n -")

    # Strip any leaked [CASE-N] labels — these are search-result indices and
    # must never appear in the final answer.  Prompt Rule #7 instructs the LLM
    # not to use them, but this is the defence-in-depth safety net.
    _case_tag_pat = _re.compile(r"\[CASE-\d+\]")
    final_answer = _case_tag_pat.sub("", final_answer)

    # Fallback: if streaming missed the answer (e.g. astream_events quirk),
    # extract it from the final graph output
    if not final_answer:
        logger.warning("[agent] turn produced no answer text")

    # Post-processing: verify source relevance (informational, not blocking)
    if final_answer and final_docs:
        final_docs = verify_source_relevance(final_answer, final_docs)

    # Build sources — include court decision metadata when present
    sources = []
    for d in final_docs:
        source: dict = {
            "doc_id": d["doc_id"],
            "page_numbers": [d["page"]],
            "text": d.get("text", ""),
            "chunk_id": d.get("chunk_id", ""),
        }
        # Propagate court decision fields if present (backward-compatible)
        if d.get("source_type") == "court_decision":
            source["source_type"] = "court_decision"
            source["case_number"] = d.get("case_number", "")
            source["decision_date"] = d.get("decision_date", "")
            source["court"] = d.get("court", "")
            source["category"] = d.get("category", "")
            source["ecli"] = d.get("ecli", "")
            source["legal_thesis"] = d.get("legal_thesis", "")
        sources.append(source)

    # Add web sources with a "web:" prefix to distinguish them from corpus docs
    seen_urls: set[str] = set()
    for ws in final_web_sources:
        url = ws.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        sources.append(
            {
                "doc_id": f"web:{url[:80]}",
                "page_numbers": [],
                "text": ws.get("snippet", ""),
                "url": url,
                "title": ws.get("title", ""),
            },
        )

    # Post-processing: page verification (DIFC only).
    # Checks that cited pages actually support the answer.  If a page has
    # NO_SUPPORT, the verifier tries to find a better page in the same
    # document.  This runs synchronously and is non-blocking — if it fails,
    # the original sources are preserved.
    if final_answer and sources and corpus == "difc":
        sources = verify_agent_pages(question, final_answer, sources)

    # T-01: Evidence-grounded source re-ranking (all corpora).
    # Re-ranks corpus sources by how well each cited page supports the final answer
    # (passes 1 + 2: exact keyword + fuzzy match).  Web sources are kept at the end.
    # This surfaces the most evidence-backed citations first in the UI and ensures
    # the agent's best-supported page leads when multiple pages exist per doc.
    if final_answer and sources:
        try:
            from arlc.evidence_verifier import rerank_agent_sources

            sources = rerank_agent_sources(final_answer, sources)
        except Exception as _ev_err:
            logger.warning("[agent] evidence verifier failed: %s", _ev_err)

    logger.info(
        "[agent] turn complete: %d docs, %d searches, answer=%d chars",
        len(final_docs),
        final_search_count,
        len(final_answer),
    )

    if on_status:
        on_status("agent:done")

    return {
        "answer": final_answer,
        "sources": sources,
        "accumulated_docs": final_docs,
    }
