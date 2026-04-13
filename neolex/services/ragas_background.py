"""RAGAS background evaluation for production queries.

After each query SSE response is sent, an async background task calls this module
to compute faithfulness + answer_relevancy scores and push them to Langfuse as
evaluation scores on the corresponding trace.

The evaluation is:
- Non-blocking: runs the synchronous RAGAS call in a thread pool via asyncio.to_thread()
- Sampled: respects RAGAS_SAMPLE_RATE (0.0–1.0)
- Fault-tolerant: any exception is caught and logged as a warning, never propagated
- Conditional on Langfuse: silently no-ops when LANGFUSE_ENABLED is false
"""

from __future__ import annotations

import asyncio
import logging
import os
import random

from neolex.config import settings
from neolex.observability import get_langfuse, is_enabled

logger = logging.getLogger(__name__)


def _build_ragas_llm():
    """Create a RAGAS-compatible LLM via ChatAnthropicVertex + LangchainLLMWrapper.

    Mirrors the implementation in scripts/ragas_eval.py so the same model is
    used for both offline evaluation and production scoring.
    """
    from langchain_google_vertexai.model_garden import ChatAnthropicVertex
    from ragas.llms import LangchainLLMWrapper

    chat_model = ChatAnthropicVertex(
        model_name="claude-sonnet-4-6",
        project=os.environ["VERTEX_PROJECT_ID"],
        location=os.environ.get("VERTEX_LOCATION", "us-east5"),
    )
    return LangchainLLMWrapper(chat_model)


def _build_ragas_embeddings():
    """Create a RAGAS-compatible embeddings wrapper using our Qwen3 embedding model.

    Uses the same embedding model already running for retrieval — avoids OpenAI dep
    (default RAGAS embedding fallback requires OPENAI_API_KEY).
    """
    from langchain_core.embeddings import Embeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper

    from arlc.retriever import embed_document, embed_query

    class Qwen3Embeddings(Embeddings):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [embed_document(t) for t in texts]

        def embed_query(self, text: str) -> list[float]:
            return embed_query(text)

    return LangchainEmbeddingsWrapper(Qwen3Embeddings())


def _run_ragas_sync(question: str, answer: str, contexts: list[str]) -> dict[str, float]:
    """Run RAGAS faithfulness + answer_relevancy evaluation synchronously.

    Intended to be called via asyncio.to_thread() so it does not block the event loop.
    RAGAS evaluate() is CPU + network bound and uses asyncio.run() internally, which
    conflicts with an already-running loop — running in a thread avoids this.

    Returns a dict mapping metric name → float score.  Empty on any failure.
    """
    from ragas import evaluate
    from ragas.dataset_schema import EvaluationDataset, SingleTurnSample
    from ragas.metrics._answer_relevance import AnswerRelevancy
    from ragas.metrics._faithfulness import Faithfulness

    sample = SingleTurnSample(
        user_input=question,
        response=answer,
        retrieved_contexts=contexts,
    )
    dataset = EvaluationDataset(samples=[sample])
    ragas_llm = _build_ragas_llm()
    ragas_embeddings = _build_ragas_embeddings()

    result = evaluate(
        dataset=dataset,
        metrics=[Faithfulness(), AnswerRelevancy()],
        llm=ragas_llm,
        embeddings=ragas_embeddings,
        show_progress=False,
    )

    # Prefer per-sample scores (RAGAS ≥0.2) for the single sample we evaluated.
    try:
        per_sample = list(result.scores)
        if per_sample:
            return {k: float(v) for k, v in per_sample[0].items() if v is not None}
    except AttributeError:
        pass

    # Fall back to aggregate scores when per-sample API is unavailable.
    return {k: float(v) for k, v in dict(result).items() if v is not None}


async def run_ragas_eval(
    *,
    question: str,
    answer: str,
    contexts: list[str],
    trace_id: str,
    corpus: str,
    answer_type: str,
) -> None:
    """Async background task: compute RAGAS scores and push them to Langfuse.

    Designed to be fired with asyncio.create_task() after the SSE answer event
    is sent.  The user never waits for this — it runs after the response is flushed.

    Args:
        question:    The user's original query.
        answer:      The pipeline's generated answer text.
        contexts:    List of retrieved chunk texts used to generate the answer.
        trace_id:    Langfuse trace ID for the parent query trace.
        corpus:      Corpus identifier (e.g. "difc", "czech").
        answer_type: Query answer type (e.g. "free_text", "boolean").
    """
    if not is_enabled():
        logger.debug("RAGAS eval skipped (Langfuse disabled)")
        return

    if random.random() >= settings.ragas_sample_rate:  # nosec B311 — sampling rate, not crypto
        logger.debug("RAGAS eval skipped (sampled out)")
        return

    if not answer or not contexts:
        logger.debug(
            "RAGAS eval skipped (empty answer=%s, num_contexts=%d)",
            not answer,
            len(contexts),
        )
        return

    try:
        logger.debug(
            "RAGAS eval starting (corpus=%s, answer_type=%s, trace_id=%.8s…)",
            corpus,
            answer_type,
            trace_id,
        )
        scores = await asyncio.to_thread(_run_ragas_sync, question, answer, contexts)

        langfuse = get_langfuse()
        if langfuse and scores:
            for metric_name, value in scores.items():
                langfuse.create_score(
                    trace_id=trace_id,
                    name=f"ragas-{metric_name}",
                    value=value,
                    comment=f"RAGAS {metric_name} (production, corpus={corpus})",
                )
            langfuse.flush()
            logger.info(
                "RAGAS scores pushed to Langfuse (trace_id=%.8s…): %s",
                trace_id,
                {f"ragas-{k}": round(v, 4) for k, v in scores.items()},
            )

    except Exception as exc:
        logger.warning(
            "RAGAS eval failed (trace_id=%.8s…): %s",
            trace_id,
            exc,
            exc_info=True,
        )
