"""LLM manager — Anthropic SDK backend."""

import logging
import os
import time

import anthropic

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            timeout=120.0,
        )
    return _client


def call_llm(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 512,
    model: str = "claude-sonnet-4-6",
    system_blocks: list[dict] | None = None,
) -> tuple[str, float, float, float, int, int]:
    """Call Claude via Anthropic SDK with streaming.
    Returns (text, ttft_ms, total_ms, tpot_ms, input_tokens, output_tokens).
    """
    client = get_client()
    start = time.perf_counter()
    chunks: list[str] = []
    ttft_ms: float | None = None
    input_tokens = output_tokens = 0

    if system_blocks is not None:
        system_param = system_blocks
    else:
        system_param = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]

    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        temperature=0.0,
        system=system_param,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        for text in stream.text_stream:
            if ttft_ms is None:
                ttft_ms = (time.perf_counter() - start) * 1000
            chunks.append(text)
        final = stream.get_final_message()
        input_tokens = final.usage.input_tokens
        output_tokens = final.usage.output_tokens

    total_ms = (time.perf_counter() - start) * 1000
    if ttft_ms is None:
        ttft_ms = total_ms
    tpot_ms = (total_ms - ttft_ms) / max(output_tokens, 1)
    return "".join(chunks).strip(), ttft_ms, total_ms, tpot_ms, input_tokens, output_tokens
