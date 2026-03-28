"""Context-aware query rewriting for multi-turn conversations.

Follow-up questions like "Can you cite the specific article?" have no legal
entity references and break the deterministic regex router. This module
rewrites them as standalone questions before routing.

Detection is heuristic (no LLM) — the Haiku call only runs for genuine
follow-ups, so fresh well-formed questions have zero added latency.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re

logger = logging.getLogger(__name__)

# --- Follow-up detection heuristics ---

# Pronouns and generic legal references that suggest prior context is needed
_FOLLOWUP_RE = re.compile(
    r"\b(this|it|that|same|these|those|"
    r"the\s+(article|rule|law|section|clause|exception|period|requirement|provision|obligation|penalty|remedy))\b",
    re.IGNORECASE,
)

# Standalone legal entity references — question is self-contained
_STANDALONE_LEGAL_RE = re.compile(
    r"(Law\s+No\.|Article\s+\d|Regulation\s+No\.|Schedule\s+\d|"
    r"DIFC|DFSA|employment\s+law|limitation|insolvency|"
    r"CA-\d{4}|ARB-\d{4}|CFI-\d{4}|SCT-\d{4})",
    re.IGNORECASE,
)

# Question starters that almost always reference prior context
_FOLLOWUP_STARTER_RE = re.compile(
    r"^(Can you|What about|What are the|How about|And |Also |Furthermore|"
    r"So |But |Does |Is |Are there|Tell me more|Explain|Elaborate|Give me)",
    re.IGNORECASE,
)


def _is_followup(question: str, history: list[dict]) -> bool:
    """Return True if question likely references previous conversation context."""
    if not history:
        return False
    # Long queries are usually self-contained
    if len(question) > 120:
        return False
    # Has its own legal entity — can stand alone
    if _STANDALONE_LEGAL_RE.search(question):
        return False
    # Short question with reference pronoun or follow-up starter
    return bool(_FOLLOWUP_RE.search(question) or _FOLLOWUP_STARTER_RE.match(question))


async def rewrite_for_retrieval(question: str, history: list[dict]) -> str:
    """Rewrite a follow-up question as a standalone legal question.

    Returns the original question unchanged if:
    - history is empty
    - heuristics say it's not a follow-up
    - Haiku call fails (graceful degradation)
    """
    if not _is_followup(question, history):
        return question

    # Build compact context from last 3 Q&A pairs (6 turns max)
    ctx_turns = history[-6:]
    ctx_lines = []
    for turn in ctx_turns:
        role = "User" if turn["role"] == "user" else "Assistant"
        content = turn["content"]
        if len(content) > 500:
            content = content[:500] + "…"
        ctx_lines.append(f"{role}: {content}")
    context_str = "\n".join(ctx_lines)

    prompt = (
        f"Previous conversation:\n{context_str}\n\n"
        f"Follow-up question: {question}\n\n"
        f"Rewrite the follow-up as a complete, standalone legal research question "
        f"that includes all necessary context (law names, article numbers, topics) "
        f"from the conversation above. Output only the rewritten question, nothing else."
    )

    try:
        rewritten = await asyncio.to_thread(_call_haiku, prompt)
        rewritten = rewritten.strip().strip('"').strip()
        if rewritten and len(rewritten) > 5:
            logger.info("Rewrote follow-up: %r → %r", question[:60], rewritten[:80])
            return rewritten
    except Exception:
        logger.exception("Haiku rewrite failed, using original question")

    return question


def _call_haiku(prompt: str) -> str:
    """Synchronous Haiku call via Vertex AI (run in thread via asyncio.to_thread)."""
    from anthropic import AnthropicVertex

    client = AnthropicVertex(
        project_id=os.environ["VERTEX_PROJECT_ID"],
        region=os.environ.get("VERTEX_LOCATION", "us-east5"),
    )
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=150,
        temperature=0.0,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
