"""Multi-endpoint LLM backend with round-robin load balancing.

Uses multiple Vertex AI endpoints via LiteLLM proxy to distribute load
and avoid per-project rate limits. Falls back gracefully if endpoints
are unavailable.

Endpoint configuration via env vars:
  LITELLM_BASE_URL   / LITELLM_API_KEY   / LITELLM_MODEL_PREFIX   — endpoint 1
  LITELLM_BASE_URL_2 / LITELLM_API_KEY_2 / LITELLM_MODEL_PREFIX_2 — endpoint 2
  LITELLM_BASE_URL_3 / LITELLM_API_KEY_3 / LITELLM_MODEL_PREFIX_3 — endpoint 3
  LITELLM_CUSTOMER_ID_N — optional x-litellm-customer-id header
"""

import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

_endpoints: list[dict] = []
_clients: list = []  # cached OpenAI clients per endpoint
_call_count = 0
_initialized = False
_init_lock = threading.Lock()

# Model name mapping: Anthropic SDK names → proxy names
_MODEL_MAP = {
    "claude-sonnet-4-6": "claude-sonnet-4-6",
    "claude-opus-4-6": "claude-opus-4-6",
    "claude-haiku-4-5": "claude-haiku-4-5",
}


def init():
    """Initialize endpoints from env vars. Call once (idempotent)."""
    global _endpoints, _initialized
    with _init_lock:
        if _initialized:
            return
        for suffix in ["", "_2", "_3"]:
            base = os.environ.get(f"LITELLM_BASE_URL{suffix}", "")
            key = os.environ.get(f"LITELLM_API_KEY{suffix}", "")
            prefix = os.environ.get(f"LITELLM_MODEL_PREFIX{suffix}", "vertex_ai")
            customer_id = os.environ.get(f"LITELLM_CUSTOMER_ID{suffix}", "")
            if base and key:
                ep: dict = {
                    "base_url": base,
                    "api_key": key,
                    "model_prefix": prefix,
                    "extra_headers": {},
                }
                if customer_id:
                    ep["extra_headers"]["x-litellm-customer-id"] = customer_id
                _endpoints.append(ep)
        # Pre-create OpenAI clients (one per endpoint, reused across calls)
        from openai import OpenAI

        for ep in _endpoints:
            extra_headers = ep.get("extra_headers", {})
            _clients.append(
                OpenAI(
                    api_key=ep["api_key"],
                    base_url=ep["base_url"],
                    default_headers=extra_headers if extra_headers else None,
                    timeout=120.0,
                )
            )
        _initialized = True
        if _endpoints:
            logger.info(f"[litellm] {len(_endpoints)} proxy endpoints configured")
        else:
            logger.debug("[litellm] No proxy endpoints configured")


def is_configured() -> bool:
    """Return True if at least one LiteLLM proxy endpoint is configured."""
    init()
    return len(_endpoints) > 0


def call_llm(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 512,
    model: str = "claude-sonnet-4-6",
    system_blocks: list[dict] | None = None,
    on_token=None,
) -> tuple[str, float, float, float, int, int]:
    """Call LLM via the next available proxy endpoint (round-robin).

    Returns (text, ttft_ms, total_ms, tpot_ms, input_tokens, output_tokens).
    """
    global _call_count
    init()
    if not _endpoints:
        raise RuntimeError("No LiteLLM proxy endpoints configured")

    if system_blocks:
        sys_text = "\n\n".join(b.get("text", "") for b in system_blocks if b.get("text"))
    else:
        sys_text = system_prompt or "You are a helpful assistant."

    base_model = _MODEL_MAP.get(model, model)
    n_eps = len(_endpoints)
    last_exc = None

    # Try each endpoint (starting from round-robin position, failing over to next)
    for attempt in range(n_eps):
        idx = (_call_count + attempt) % n_eps
        ep = _endpoints[idx]
        client = _clients[idx]
        litellm_model = f"{ep['model_prefix']}/{base_model}"

        try:
            start = time.perf_counter()
            ttft_ms: float | None = None
            chunks: list[str] = []
            input_tokens = output_tokens = 0

            stream = client.chat.completions.create(
                model=litellm_model,
                max_tokens=max_tokens,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": sys_text},
                    {"role": "user", "content": user_message},
                ],
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    if ttft_ms is None:
                        ttft_ms = (time.perf_counter() - start) * 1000
                    chunks.append(delta.content)
                    if on_token is not None:
                        on_token(delta.content)
                if hasattr(chunk, "usage") and chunk.usage:
                    input_tokens = getattr(chunk.usage, "prompt_tokens", 0) or 0
                    output_tokens = getattr(chunk.usage, "completion_tokens", 0) or 0

            total_ms = (time.perf_counter() - start) * 1000
            if ttft_ms is None:
                ttft_ms = total_ms
            tpot_ms = (total_ms - ttft_ms) / max(output_tokens, 1)

            result_text = "".join(chunks).strip()
            _call_count += 1  # advance round-robin only on success
            logger.debug(
                "[litellm] model=%s endpoint=%d ttft=%.0fms total=%.0fms",
                litellm_model,
                idx,
                ttft_ms,
                total_ms,
            )
            return result_text, ttft_ms, total_ms, tpot_ms, input_tokens, output_tokens

        except Exception as exc:
            last_exc = exc
            logger.warning("[litellm] endpoint %d failed: %s", idx, str(exc)[:120])
            if attempt < n_eps - 1:
                time.sleep(1)  # brief pause before failover
                continue

    _call_count += 1  # advance even on total failure

    # Last resort: fall back to Vertex AI directly if configured
    from arlc.llm import vertex_backend

    if vertex_backend.is_configured():
        logger.warning("[litellm] All proxy endpoints failed — falling back to Vertex AI directly")
        return vertex_backend.call_llm(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=max_tokens,
            model=model,
            system_blocks=system_blocks,
        )

    raise last_exc  # type: ignore[misc]
