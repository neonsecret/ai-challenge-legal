"""LLM router — delegates to the configured LLM backend with retry logic.

Backend selection via LLM_BACKEND env var:
  - "litellm" (default): use LiteLLM proxy (round-robin across endpoints)
  - "vertex": use Vertex AI (AnthropicVertex client)
  - "anthropic": use Anthropic SDK directly
  - "auto": try litellm first, then vertex, then anthropic
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

    choice = os.environ.get("LLM_BACKEND", "litellm").lower()
    if choice == "auto":
        # Try litellm first (multi-endpoint), then vertex, then anthropic
        from arlc.llm import litellm_backend

        if litellm_backend.is_configured():
            _backend = "litellm"
            logger.info("[LLM] auto-detected backend: litellm")
        else:
            from arlc.llm import vertex_backend as llm_vertex

            if llm_vertex.is_configured():
                _backend = "vertex"
                logger.info("[LLM] auto-detected backend: vertex")
            else:
                _backend = "anthropic"
                logger.info("[LLM] auto-detected backend: anthropic")
    elif choice in ("litellm", "vertex", "anthropic"):
        _backend = choice
    else:
        logger.warning(f"[LLM] Unknown LLM_BACKEND={choice!r}, falling back to litellm")
        _backend = "litellm"
    return _backend


def _call_backend(
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    model: str,
    system_blocks: list[dict] | None,
) -> tuple[str, float, float, float, int, int]:
    backend = _get_backend()
    if backend == "litellm":
        from arlc.llm import litellm_backend

        return litellm_backend.call_llm(
            system_prompt,
            user_message,
            max_tokens,
            model=model,
            system_blocks=system_blocks,
        )
    if backend == "vertex":
        from arlc.llm import vertex_backend as llm_vertex

        return llm_vertex.call_llm(
            system_prompt,
            user_message,
            max_tokens,
            model=model,
            system_blocks=system_blocks,
        )
    from arlc.llm import anthropic_backend as llm_anthropic

    return llm_anthropic.call_llm(
        system_prompt,
        user_message,
        max_tokens,
        model=model,
        system_blocks=system_blocks,
    )


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "rate limit" in msg or "overloaded" in msg or "resource_exhausted" in msg


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
                system_prompt,
                user_message,
                max_tokens,
                model=model,
                system_blocks=system_blocks,
            )
        except Exception as exc:
            last_exc = exc
            logger.warning(f"[LLM] Attempt {attempt + 1} failed: {exc}")
            if _is_rate_limit(exc):
                continue
            if attempt >= MAX_RETRIES:
                break

    raise last_exc  # type: ignore[misc]
