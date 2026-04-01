"""Generate contextual follow-up questions using Haiku with structured output."""

import asyncio
import json
import logging
import os

logger = logging.getLogger(__name__)

# Use Haiku for fast, cheap follow-up generation
_HAIKU_MODEL = "claude-haiku-4-5"

# Tool definition for structured output via Anthropic tool_use API
_FOLLOW_UPS_TOOL = {
    "name": "suggest_follow_ups",
    "description": "Suggest 3-4 contextual follow-up questions based on the legal Q&A.",
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 3,
                "maxItems": 4,
                "description": "Follow-up questions, each under 60 characters.",
            }
        },
        "required": ["questions"],
    },
}

# Jurisdiction display names used in the prompt
_JURISDICTION_NAMES: dict[str, str] = {
    "difc": "DIFC (Dubai International Financial Centre)",
    "uk": "United Kingdom",
    "au": "Australia",
    "czech": "Czech Republic",
}

# How long to wait for Haiku before giving up (seconds)
_TIMEOUT_SECONDS = 3.0

# Client singletons — initialised lazily per backend
_anthropic_client = None
_vertex_client = None


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic

        _anthropic_client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            timeout=10.0,
        )
    return _anthropic_client


def _get_vertex_client():
    global _vertex_client
    if _vertex_client is None:
        from anthropic import AnthropicVertex

        _vertex_client = AnthropicVertex(
            project_id=os.environ["VERTEX_PROJECT_ID"],
            region=os.environ.get("VERTEX_LOCATION", "us-east5"),
        )
    return _vertex_client


def _build_prompt(question: str, answer: str, corpus: str) -> tuple[str, str]:
    """Return (system, user) prompts for follow-up generation."""
    jurisdiction = _JURISDICTION_NAMES.get(corpus, corpus)
    system = (
        "You are a legal research assistant helping a lawyer dig deeper into an answer. "
        "Generate 3-4 follow-up questions that:\n"
        "- Reference specific laws, articles, sections, or parties mentioned in the answer\n"
        "- Explore practical implications or edge cases not yet covered\n"
        "- Are jurisdiction-aware (do NOT suggest comparing to the jurisdiction already in use)\n"
        "- Are concise: under 60 characters each\n"
        f"- Are relevant to {jurisdiction} law"
    )
    user = f"User question: {question}\n\nAI answer (excerpt): {answer[:2000]}\n\nSuggest 3-4 follow-up questions."
    return system, user


def _call_with_tool_use(client, question: str, answer: str, corpus: str) -> list[str]:
    """Call Haiku via Anthropic SDK (Vertex or direct) using tool_use structured output."""
    system, user = _build_prompt(question, answer, corpus)
    response = client.messages.create(
        model=_HAIKU_MODEL,
        max_tokens=256,
        temperature=0.0,
        system=system,
        messages=[{"role": "user", "content": user}],
        tools=[_FOLLOW_UPS_TOOL],
        tool_choice={"type": "tool", "name": "suggest_follow_ups"},
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "suggest_follow_ups":
            questions = block.input.get("questions", [])
            return [q for q in questions if isinstance(q, str) and len(q) <= 80][:4]
    # No tool_use block — should not happen with forced tool_choice, but be safe
    return []


def _call_via_litellm(question: str, answer: str, corpus: str) -> list[str]:
    """Call Haiku via LiteLLM proxy with JSON prompt (OpenAI-compatible interface)."""
    from arlc.llm import litellm_backend

    system, user = _build_prompt(question, answer, corpus)
    json_user = (
        user + "\n\nReply ONLY with valid JSON (no markdown, no explanation): "
        '{"questions": ["<question 1>", "<question 2>", "<question 3>"]}'
    )
    text, *_ = litellm_backend.call_llm(
        system_prompt=system,
        user_message=json_user,
        max_tokens=256,
        model=_HAIKU_MODEL,
    )
    # Strip markdown code fences if present
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    data = json.loads(stripped)
    questions = data.get("questions", [])
    return [q for q in questions if isinstance(q, str) and len(q) <= 80][:4]


def _generate_sync(question: str, answer: str, corpus: str) -> list[str]:
    """Synchronous follow-up generation — call from asyncio.to_thread."""
    backend = os.environ.get("LLM_BACKEND", "litellm").lower()

    # LiteLLM (OpenAI-compatible proxy) — JSON prompt path
    if backend == "litellm":
        from arlc.llm import litellm_backend

        if litellm_backend.is_configured():
            return _call_via_litellm(question, answer, corpus)

    # Vertex AI — tool_use path
    if backend == "vertex" or (backend == "auto" and os.environ.get("VERTEX_PROJECT_ID")):
        return _call_with_tool_use(_get_vertex_client(), question, answer, corpus)

    # Direct Anthropic SDK — tool_use path
    return _call_with_tool_use(_get_anthropic_client(), question, answer, corpus)


async def generate_follow_ups(question: str, answer: str, corpus: str) -> list[str]:
    """Generate 3-4 contextual follow-up questions using Haiku.

    Returns an empty list on error or timeout — the caller should fall back
    to static suggestions rather than failing the whole response.
    """
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_generate_sync, question, answer, corpus),
            timeout=_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("[follow_ups] Haiku call timed out after %.1fs", _TIMEOUT_SECONDS)
        return []
    except Exception:
        logger.warning("[follow_ups] generate_follow_ups failed", exc_info=True)
        return []
