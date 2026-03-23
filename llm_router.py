"""LLM router — delegates to the configured LLM backend with retry logic.

Backend selection via LLM_BACKEND env var:
  - "anthropic" (default): use Anthropic SDK directly
  - "vertex": use Vertex AI (AnthropicVertex client)
  - "auto": try Vertex first if configured, fall back to Anthropic SDK
"""

import logging
import os
import time

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [10, 30, 60]

_backend: str | None = None


def _get_backend() -> str:
    """Resolve the LLM backend to use."""
    global _backend
    if _backend is not None:
        return _backend

    choice = os.environ.get("LLM_BACKEND", "anthropic").lower()
    if choice == "auto":
        import llm_vertex
        _backend = "vertex" if llm_vertex.is_configured() else "anthropic"
        logger.info(f"[LLM] auto-detected backend: {_backend}")
    elif choice in ("vertex", "anthropic"):
        _backend = choice
    else:
        logger.warning(f"[LLM] Unknown LLM_BACKEND={choice!r}, falling back to anthropic")
        _backend = "anthropic"
    return _backend


def _call_backend(
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    model: str,
    system_blocks: list[dict] | None,
) -> tuple[str, float, float, float, int, int]:
    backend = _get_backend()
    if backend == "vertex":
        import llm_vertex
        return llm_vertex.call_llm(
            system_prompt, user_message, max_tokens,
            model=model, system_blocks=system_blocks,
        )
    else:
        import llm_anthropic
        return llm_anthropic.call_llm(
            system_prompt, user_message, max_tokens,
            model=model, system_blocks=system_blocks,
        )


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "rate limit" in msg or "overloaded" in msg


def call_llm(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 512,
    model: str = "claude-sonnet-4-6",
    system_blocks: list[dict] | None = None,
) -> tuple[str, float, float, float, int, int]:
    """Call LLM via the configured backend with retry logic."""
    last_exc = None
    for attempt in range(1 + MAX_RETRIES):
        if attempt > 0:
            time.sleep(min(RETRY_DELAYS[attempt - 1], 30))
        try:
            return _call_backend(
                system_prompt, user_message, max_tokens,
                model=model, system_blocks=system_blocks,
            )
        except Exception as exc:
            last_exc = exc
            logger.warning(f"[LLM] Attempt {attempt + 1} failed: {exc}")
            if _is_rate_limit(exc):
                continue
            if attempt >= MAX_RETRIES:
                break

    raise last_exc  # type: ignore[misc]
