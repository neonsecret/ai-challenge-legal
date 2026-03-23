"""LLM router — delegates to the Anthropic SDK backend with retry logic."""

import logging
import time

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [10, 30, 60]


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
    """Call LLM via Anthropic SDK with retry logic."""
    import llm_anthropic

    last_exc = None
    for attempt in range(1 + MAX_RETRIES):
        if attempt > 0:
            time.sleep(min(RETRY_DELAYS[attempt - 1], 30))
        try:
            return llm_anthropic.call_llm(
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
