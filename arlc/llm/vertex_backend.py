"""LLM manager — Vertex AI backend (AnthropicVertex client)."""

import os
import time
import logging

from anthropic import AnthropicVertex

logger = logging.getLogger(__name__)

_client: AnthropicVertex | None = None


def get_client() -> AnthropicVertex:
    global _client
    if _client is None:
        _client = AnthropicVertex(
            project_id=os.environ["VERTEX_PROJECT_ID"],
            region=os.environ.get("VERTEX_LOCATION", "us-east5"),
        )
    return _client


def is_configured() -> bool:
    """Return True if Vertex AI env vars are present."""
    return bool(os.environ.get("VERTEX_PROJECT_ID"))


def call_llm(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 512,
    model: str = "claude-sonnet-4-6",
    system_blocks: list[dict] | None = None,
) -> tuple[str, float, float, float, int, int]:
    """Call Claude via Vertex AI with streaming.
    Returns (text, ttft_ms, total_ms, tpot_ms, input_tokens, output_tokens).
    """
    client = get_client()
    start = time.perf_counter()
    chunks: list[str] = []
    ttft_ms: float | None = None
    input_tokens = output_tokens = 0

    if system_blocks is not None:
        system_param = system_blocks
    elif system_prompt:
        system_param = [{"type": "text", "text": system_prompt,
                         "cache_control": {"type": "ephemeral"}}]
    else:
        system_param = []  # Vertex rejects cache_control on empty text blocks

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
