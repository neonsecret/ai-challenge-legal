"""Langfuse observability for Vitreon Legal.

Provides per-query tracing with nested spans for retrieval, reranking,
and LLM generation. All traces are sent to a self-hosted Langfuse v3
instance (localhost:3040).

Enable by setting LANGFUSE_ENABLED=true in .env (disabled by default).
When disabled, all public functions are zero-cost no-ops.

Required env vars when enabled:
    LANGFUSE_PUBLIC_KEY  - from langfuse project settings
    LANGFUSE_SECRET_KEY  - from langfuse project settings
    LANGFUSE_HOST        - langfuse URL (default: http://localhost:3040)

Uses Langfuse SDK v4 (OTEL-based) + opentelemetry-instrumentation-langchain
for automatic per-step agent tracing.  Trace-level input/output and user
metadata are set via ``set_trace_io`` and ``propagate_attributes`` so the
Langfuse UI renders them correctly (no more "didn't receive an input or
output" warnings).
"""

from __future__ import annotations

import contextvars
import logging
import os
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ContextVar — propagates the active trace across async + thread boundaries.
# asyncio.to_thread() copies the current context, so the trace set in the
# main coroutine is visible inside executor-submitted callables automatically.
# Use set_current_trace() / get_current_trace() instead of passing trace
# explicitly through every function signature.
# ---------------------------------------------------------------------------

_current_trace: contextvars.ContextVar[Any] = contextvars.ContextVar("langfuse_trace", default=None)


def set_current_trace(trace: Any) -> contextvars.Token:
    """Set the active Langfuse trace for the current context.

    Returns a Token that can be passed to reset_current_trace() to restore
    the previous value (useful when nesting traces).
    """
    return _current_trace.set(trace)


def reset_current_trace(token: contextvars.Token) -> None:
    """Restore the previous trace value using the token from set_current_trace()."""
    _current_trace.reset(token)


def get_current_trace() -> Any:
    """Return the active Langfuse trace for the current context, or None."""
    return _current_trace.get()


# ---------------------------------------------------------------------------
# Per-tool-call span ContextVar — propagates the active tool span into threads
# so retrieval sub-spans can be nested under the parent tool span.
# asyncio.to_thread() copies the current context automatically, so setting
# this before the call makes it visible inside the worker thread.
# ---------------------------------------------------------------------------

_current_span: contextvars.ContextVar[Any] = contextvars.ContextVar("langfuse_span", default=None)


def set_current_span(span: Any) -> contextvars.Token:
    """Set the active Langfuse tool span for the current context."""
    return _current_span.set(span)


def reset_current_span(token: contextvars.Token) -> None:
    """Restore the previous span value."""
    _current_span.reset(token)


def get_current_span() -> Any:
    """Return the active Langfuse tool span, or None."""
    return _current_span.get()


# ---------------------------------------------------------------------------
# Cost model — per-million-token prices (USD) for each supported model
# ---------------------------------------------------------------------------

MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-6": {
        "input": 5.00,
        "cache_write": 6.25,
        "cache_read": 0.50,
        "output": 25.00,
    },
    "claude-sonnet-4-6": {
        "input": 3.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
        "output": 15.00,
    },
    "claude-haiku-4-5": {
        "input": 1.00,
        "cache_write": 1.25,
        "cache_read": 0.10,
        "output": 5.00,
    },
}

# Max chars for tool-call inputs (queries, ECLI refs, etc.) recorded in agent step spans.
# Imported by arlc modules that add generation spans for their LLM calls.
_SPAN_INPUT_TRUNCATE_CHARS = 500

# Max chars of LLM prompt text recorded in generation spans.
# Legal RAG prompts contain full statute/judgment text and can exceed 50k chars.
# 100k covers the vast majority of prompts while bounding Langfuse payload size.
_GEN_INPUT_TRUNCATE_CHARS = 100_000


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Return estimated USD cost for a Claude API call.

    Uses MODEL_PRICING per-MTok rates. Returns 0.0 for unknown models
    so callers never see None or an exception.
    """
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        return 0.0
    per_m = 1_000_000
    cost = (
        input_tokens * pricing["input"] / per_m
        + output_tokens * pricing["output"] / per_m
        + cache_read_tokens * pricing["cache_read"] / per_m
        + cache_write_tokens * pricing["cache_write"] / per_m
    )
    return round(cost, 8)


# Module-level singleton — set by init_observability().
_langfuse_client = None
_enabled = False
_langchain_instrumented = False


def init_observability() -> bool:
    """Initialize Langfuse client if enabled. Safe to call multiple times.

    Also enables OpenTelemetry auto-instrumentation for LangChain/LangGraph
    so every agent step (LLM call, tool call, chain execution) is captured
    as a span in Langfuse automatically.

    Returns True if successfully initialized, False otherwise.
    """
    global _langfuse_client, _enabled, _langchain_instrumented

    if _enabled and _langfuse_client is not None:
        return True

    if os.environ.get("LANGFUSE_ENABLED", "").lower() not in ("1", "true", "yes"):
        logger.debug("Langfuse observability disabled (set LANGFUSE_ENABLED=true)")
        return False

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    host = os.environ.get("LANGFUSE_HOST", "http://localhost:3040")

    if not public_key or not secret_key:
        logger.warning("Langfuse enabled but keys not set — skipping")
        return False

    try:
        from langfuse import Langfuse

        client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        # Validate connection
        client.auth_check()

        _langfuse_client = client
        _enabled = True
        logger.info("Langfuse observability initialized (host=%s)", host)

        # Auto-instrument LangChain/LangGraph via OpenTelemetry.
        # This captures every LLM invocation, tool call, and chain step
        # as OTEL spans which Langfuse exports automatically.
        if not _langchain_instrumented:
            try:
                from opentelemetry.instrumentation.langchain import (
                    LangchainInstrumentor,
                )

                LangchainInstrumentor().instrument()
                _langchain_instrumented = True
                logger.info("LangChain OTEL auto-instrumentation enabled")
            except ImportError:
                logger.info(
                    "opentelemetry-instrumentation-langchain not installed — agent steps will use manual spans only"
                )
            except Exception as exc:
                logger.warning("LangChain OTEL instrumentation failed: %s", exc)

        return True

    except ImportError:
        logger.warning("langfuse package not installed")
        return False
    except Exception as exc:
        logger.warning("Failed to initialize langfuse: %s", exc)
        return False


def shutdown_observability() -> None:
    """Flush pending events and shut down. Called at app shutdown."""
    global _langfuse_client, _enabled
    if _langfuse_client is not None:
        try:
            _langfuse_client.flush()
        except Exception:
            logger.debug("Langfuse flush on shutdown failed", exc_info=True)
    _langfuse_client = None
    _enabled = False


def is_enabled() -> bool:
    """Return True if Langfuse tracing is active."""
    return _enabled


def get_langfuse():
    """Return the Langfuse client singleton, or None if disabled."""
    return _langfuse_client


def get_trace_id(trace) -> str | None:
    """Extract the Langfuse trace ID from a root span.

    Returns the trace-level ID (not the span ID) so callers can attach
    scores or link external evaluations to the trace.
    """
    if trace is None:
        return None
    return getattr(trace, "trace_id", None)


# ---------------------------------------------------------------------------
# Trace / span helpers — all no-ops when disabled
# ---------------------------------------------------------------------------


def create_query_trace(
    *,
    session_id: str | None = None,
    user_id: str | None = None,
    user_email: str | None = None,
    user_name: str | None = None,
    subscription_plan: str | None = None,
    query: str,
    corpus: str,
    answer_type: str = "",
    use_agent: bool = True,
    metadata: dict[str, Any] | None = None,
) -> Any | None:
    """Create a top-level Langfuse trace for a user query.

    Uses ``propagate_attributes`` so the trace-level ``user_id`` and
    ``session_id`` are set (enabling grouping/filtering in the Langfuse
    UI), then creates a root span whose input is also propagated to the
    trace via ``set_trace_io``.

    Returns a LangfuseSpan object (or None when disabled) that can be
    passed to span helpers below.
    """
    if not _enabled or _langfuse_client is None:
        return None

    try:
        from langfuse import propagate_attributes

        trace_input = {"question": query, "corpus": corpus, "answer_type": answer_type}
        trace_metadata = {
            "corpus": corpus,
            "answer_type": answer_type,
            "use_agent": use_agent,
            **(metadata or {}),
        }
        if user_email:
            trace_metadata["user_email"] = user_email
        if user_name:
            trace_metadata["user_name"] = user_name
        if subscription_plan:
            trace_metadata["subscription_plan"] = subscription_plan

        # Build tags for quick filtering in the Langfuse UI.
        tags = [f"corpus:{corpus}"]
        if use_agent:
            tags.append("agent")

        # propagate_attributes sets trace-level user_id, session_id, and
        # tags so they are visible in the Langfuse trace list (not buried
        # in span metadata).  The metadata kwarg expects Dict[str, str],
        # so we pass only string-valued items here; the full metadata
        # (including booleans/ints) goes on the span itself.
        propagate_meta = {k: str(v) for k, v in trace_metadata.items() if isinstance(v, str)}
        with propagate_attributes(
            user_id=user_id or None,
            session_id=session_id or None,
            tags=tags,
            trace_name="vitreon-query",
            metadata=propagate_meta,
        ):
            obs = _langfuse_client.start_observation(
                name="vitreon-query",
                as_type="span",
                input=trace_input,
                metadata=trace_metadata,
            )

        # Set trace-level input so Langfuse shows it on the trace itself,
        # not just on the root span.  This fixes the "Looks like this
        # trace didn't receive an input or output" warning.
        obs.set_trace_io(input=trace_input)

        return obs
    except Exception:
        logger.debug("Failed to create langfuse trace", exc_info=True)
        return None


def add_retrieval_span(
    trace,
    *,
    query: str,
    num_results: int = 0,
    duration_ms: float = 0,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record a retrieval span on an existing trace."""
    if trace is None:
        return
    try:
        span = trace.start_observation(
            name="retrieval",
            as_type="span",
            input={"query": query},
        )
        span.update(
            output={"num_results": num_results},
            metadata={"duration_ms": round(duration_ms, 1), **(metadata or {})},
        )
        span.end()
    except Exception:
        logger.debug("Failed to add retrieval span", exc_info=True)


def add_reranking_span(
    trace,
    *,
    num_candidates: int = 0,
    num_results: int = 0,
    duration_ms: float = 0,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record a reranking span on an existing trace."""
    if trace is None:
        return
    try:
        span = trace.start_observation(
            name="reranking",
            as_type="span",
            input={"num_candidates": num_candidates},
        )
        span.update(
            output={"num_results": num_results},
            metadata={"duration_ms": round(duration_ms, 1), **(metadata or {})},
        )
        span.end()
    except Exception:
        logger.debug("Failed to add reranking span", exc_info=True)


def add_generation_span(
    trace,
    *,
    model: str = "claude-sonnet-4-6",
    input_text: str = "",
    output_text: str = "",
    duration_ms: float = 0,
    usage: dict[str, int] | None = None,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record an LLM generation span on an existing trace.

    Automatically computes cost_usd from token counts when usage is provided,
    using MODEL_PRICING rates for the given model.
    """
    if trace is None:
        return
    try:
        gen = trace.start_observation(
            name="llm-generation",
            as_type="generation",
            model=model,
            input=input_text[:_GEN_INPUT_TRUNCATE_CHARS] if input_text else "",
        )
        span_metadata: dict[str, Any] = {"duration_ms": round(duration_ms, 1), **(metadata or {})}
        if usage:
            cost = calculate_cost(
                model,
                input_tokens=usage.get("input", 0),
                output_tokens=usage.get("output", 0),
                cache_read_tokens=cache_read_tokens,
                cache_write_tokens=cache_write_tokens,
            )
            if cost > 0:
                span_metadata["cost_usd"] = cost
        update_kwargs: dict[str, Any] = {
            "output": output_text[:5000] if output_text else "",
            "metadata": span_metadata,
        }
        if usage:
            update_kwargs["usage_details"] = usage
        gen.update(**update_kwargs)
        gen.end()
    except Exception:
        logger.debug("Failed to add generation span", exc_info=True)


def add_agent_step_span(
    trace,
    *,
    step_name: str,
    step_type: str = "span",
    input_data: Any = None,
    output_data: Any = None,
    metadata: dict[str, Any] | None = None,
    model: str | None = None,
) -> None:
    """Record a single agent step (reason, search, tool call) as a span."""
    if trace is None:
        return
    try:
        kwargs: dict[str, Any] = {
            "name": step_name,
            "as_type": step_type,
        }
        if input_data is not None:
            kwargs["input"] = input_data
        if model:
            kwargs["model"] = model

        span = trace.start_observation(**kwargs)
        update_kwargs: dict[str, Any] = {}
        if output_data is not None:
            update_kwargs["output"] = output_data
        if metadata:
            update_kwargs["metadata"] = metadata
        if update_kwargs:
            span.update(**update_kwargs)
        span.end()
    except Exception:
        logger.debug("Failed to add agent step span", exc_info=True)


def start_tool_span(
    trace,
    *,
    name: str,
    input_data: Any = None,
    metadata: dict[str, Any] | None = None,
) -> Any | None:
    """Open a named tool span on the trace and return it (caller must call end_tool_span).

    Unlike add_agent_step_span(), this span stays open so retrieval sub-spans
    (bm25-retrieval, vector-retrieval, reranking) can be recorded as children
    while the tool executes inside asyncio.to_thread().
    """
    if trace is None or not _enabled:
        return None
    try:
        kwargs: dict[str, Any] = {"name": name, "as_type": "span"}
        if input_data is not None:
            kwargs["input"] = input_data
        if metadata:
            kwargs["metadata"] = metadata
        return trace.start_observation(**kwargs)
    except Exception:
        logger.debug("Failed to start tool span %s", name, exc_info=True)
        return None


def end_tool_span(
    span,
    *,
    output_data: Any = None,
    metadata: dict[str, Any] | None = None,
    level: str = "DEFAULT",
) -> None:
    """Finalise a tool span opened by start_tool_span()."""
    if span is None:
        return
    try:
        update_kwargs: dict[str, Any] = {"level": level}
        if output_data is not None:
            update_kwargs["output"] = output_data
        if metadata:
            update_kwargs["metadata"] = metadata
        span.update(**update_kwargs)
        span.end()
    except Exception:
        logger.debug("Failed to end tool span", exc_info=True)


def add_retrieval_substep_span(
    *,
    name: str,
    input_data: Any = None,
    output_data: Any = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Record a retrieval sub-step as a child of the current tool span.

    Falls back to the root trace when no tool span is active.
    asyncio.to_thread() copies the Python context, so _current_span set in
    the async task is visible in the worker thread without extra plumbing.

    Produces the nested hierarchy::

        SPAN tool:search_legal_corpus
        ├── SPAN bm25-retrieval
        ├── SPAN vector-retrieval
        └── SPAN reranking
    """
    if not _enabled:
        return
    parent = get_current_span() or get_current_trace()
    if parent is None:
        return
    try:
        kwargs: dict[str, Any] = {"name": name, "as_type": "span"}
        if input_data is not None:
            kwargs["input"] = input_data
        obs = parent.start_observation(**kwargs)
        update_kwargs: dict[str, Any] = {}
        if output_data is not None:
            update_kwargs["output"] = output_data
        if metadata:
            update_kwargs["metadata"] = metadata
        if update_kwargs:
            obs.update(**update_kwargs)
        obs.end()
    except Exception:
        logger.debug("Failed to add retrieval sub-span %s", name, exc_info=True)


def finalize_trace(
    trace,
    *,
    output: str | None = None,
    metadata: dict[str, Any] | None = None,
    level: str = "DEFAULT",
) -> None:
    """Update a trace with final output and status, then end it.

    Sets output on both the root span and the parent trace (via
    ``set_trace_io``) so the Langfuse UI displays it at the trace level.
    """
    if trace is None:
        return
    try:
        truncated_output = output[:5000] if output else None
        update_kwargs: dict[str, Any] = {"level": level}
        if truncated_output is not None:
            update_kwargs["output"] = truncated_output
        if metadata:
            update_kwargs["metadata"] = metadata
        trace.update(**update_kwargs)

        # Propagate output to the trace level so the Langfuse trace list
        # shows the answer inline (not just nested inside the root span).
        if truncated_output is not None:
            trace.set_trace_io(output=truncated_output)

        trace.end()
    except Exception:
        logger.debug("Failed to finalize langfuse trace", exc_info=True)


@contextmanager
def trace_query_context(
    *,
    session_id: str | None = None,
    user_id: str | None = None,
    user_email: str | None = None,
    user_name: str | None = None,
    subscription_plan: str | None = None,
    query: str,
    corpus: str,
    answer_type: str = "",
    use_agent: bool = True,
    metadata: dict[str, Any] | None = None,
):
    """Context manager that creates a trace, yields it, and finalizes on exit.

    Usage::

        with trace_query_context(query=q, corpus=c, ...) as trace:
            # ... run pipeline ...
            add_retrieval_span(trace, ...)
            add_generation_span(trace, ...)
            finalize_trace(trace, output=answer)
    """
    trace = create_query_trace(
        session_id=session_id,
        user_id=user_id,
        user_email=user_email,
        user_name=user_name,
        subscription_plan=subscription_plan,
        query=query,
        corpus=corpus,
        answer_type=answer_type,
        use_agent=use_agent,
        metadata=metadata,
    )
    try:
        yield trace
    except Exception:
        if trace is not None:
            finalize_trace(trace, level="ERROR", metadata={"error": True})
        raise
