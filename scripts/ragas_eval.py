#!/usr/bin/env python3
"""RAGAS evaluation script for Vitreon Legal RAG pipeline.

Runs reference-free evaluation metrics (faithfulness, answer relevancy)
on a sample of questions through our pipeline.

When LANGFUSE_ENABLED=true, each sample creates a Langfuse trace and
RAGAS scores are pushed as evaluation scores on the corresponding traces.

Requirements:
    uv sync --group eval        # installs ragas; also add --group observability for Langfuse tracing

Usage:
    uv run --group eval python scripts/ragas_eval.py --corpus difc --sample 10
    uv run --group eval python scripts/ragas_eval.py --corpus difc --sample 50 --metrics faithfulness answer_relevancy
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("ragas_eval")


def build_ragas_llm():
    """Create a RAGAS-compatible LLM from our Vertex AI config."""
    from anthropic import AnthropicVertex
    from ragas.llms import llm_factory

    client = AnthropicVertex(
        project_id=os.environ["VERTEX_PROJECT_ID"],
        region=os.environ.get("VERTEX_LOCATION", "us-east5"),
    )
    return llm_factory(
        model="claude-sonnet-4-6",
        provider="anthropic",
        client=client,
    )


def _get_langfuse():
    """Return a Langfuse client if enabled, else None.

    Uses the same Langfuse() constructor as the main app.  SDK v4 removed
    the legacy ``trace()`` method — traces are created via
    ``start_observation()`` with ``set_trace_io()`` instead.
    """
    if os.environ.get("LANGFUSE_ENABLED", "").lower() not in ("1", "true", "yes"):
        return None
    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
            host=os.environ.get("LANGFUSE_HOST", "http://localhost:3040"),
        )
    except Exception as exc:
        logger.warning("Langfuse not available: %s", exc)
        return None


async def run_pipeline_for_question(question: str, answer_type: str, corpus: str) -> dict:
    """Run our RAG pipeline on a single question, returning (answer, contexts)."""
    from arlc.answerer import generate_answer
    from arlc.retriever import retrieve_pages

    # Retrieve
    pages = retrieve_pages(
        question=question,
        target_doc_ids=None,
        max_per_doc=5,
        max_total=10,
        answer_type=answer_type,
        corpus=corpus,
    )
    contexts = [p.text for p in pages if p.text]

    # Answer
    source_pages = [
        {"doc_id": p.doc_id, "page_number": p.page_number, "text": p.text}
        for p in pages
    ]
    result = await generate_answer(
        question=question,
        answer_type=answer_type,
        source_pages=source_pages,
        corpus=corpus,
    )

    return {
        "question": question,
        "answer": str(result.answer) if result.answer is not None else "",
        "contexts": contexts,
        "answer_type": answer_type,
    }


async def collect_samples(
    questions: list[dict],
    corpus: str,
    sample_size: int,
    langfuse=None,
) -> tuple[list[dict], list[str]]:
    """Run pipeline on a sample of questions and collect results.

    Returns (samples, trace_ids) — trace_ids is populated only when Langfuse is enabled.
    """
    import random

    # Sample questions (prefer free_text for richer evaluation)
    free_text = [q for q in questions if q["answer_type"] == "free_text"]
    other = [q for q in questions if q["answer_type"] != "free_text"]

    # Take mix: 60% free_text, 40% other types
    n_free = min(int(sample_size * 0.6), len(free_text))
    n_other = min(sample_size - n_free, len(other))

    sampled = random.sample(free_text, n_free) + random.sample(other, n_other)
    random.shuffle(sampled)

    logger.info("Running pipeline on %d questions (corpus=%s)...", len(sampled), corpus)

    results = []
    trace_ids = []
    for i, q in enumerate(sampled):
        try:
            logger.info("[%d/%d] %s (%s)", i + 1, len(sampled), q["question"][:60], q["answer_type"])
            result = await run_pipeline_for_question(q["question"], q["answer_type"], corpus)
            results.append(result)

            # Create Langfuse trace for this eval sample.
            # SDK v4 removed langfuse.trace() — use start_observation +
            # set_trace_io to create a properly formatted trace.
            trace_id = None
            if langfuse is not None:
                try:
                    from langfuse import propagate_attributes

                    trace_input = {"question": q["question"], "corpus": corpus}
                    trace_output = {"answer": result["answer"][:2000]}
                    trace_metadata = {
                        "answer_type": q["answer_type"],
                        "num_contexts": len(result["contexts"]),
                        "eval_run": True,
                    }

                    with propagate_attributes(
                        tags=["ragas-eval", f"corpus:{corpus}"],
                        trace_name="ragas-eval-sample",
                        metadata={k: str(v) for k, v in trace_metadata.items() if isinstance(v, str)},
                    ):
                        obs = langfuse.start_observation(
                            name="ragas-eval-sample",
                            as_type="span",
                            input=trace_input,
                            output=trace_output,
                            metadata=trace_metadata,
                        )

                    obs.set_trace_io(input=trace_input, output=trace_output)
                    obs.end()
                    trace_id = obs.trace_id
                except Exception:
                    logger.debug("Failed to create langfuse trace for eval sample", exc_info=True)
            trace_ids.append(trace_id)

        except Exception as e:
            logger.error("Failed on question %s: %s", q["id"][:12], e)
            trace_ids.append(None)

    return results, trace_ids


def run_ragas_evaluation(samples: list[dict], metrics_list: list[str]) -> dict:
    """Run RAGAS evaluation on collected samples."""
    from ragas import evaluate
    from ragas.dataset_schema import EvaluationDataset, SingleTurnSample
    from ragas.metrics._answer_relevance import AnswerRelevancy
    from ragas.metrics._faithfulness import Faithfulness

    # Build metric objects
    available_metrics = {
        "faithfulness": Faithfulness,
        "answer_relevancy": AnswerRelevancy,
    }

    metrics = []
    for name in metrics_list:
        if name in available_metrics:
            metrics.append(available_metrics[name]())
        else:
            logger.warning("Unknown metric: %s (available: %s)", name, list(available_metrics.keys()))

    if not metrics:
        logger.error("No valid metrics specified")
        return {}

    # Build evaluation dataset
    eval_samples = []
    for s in samples:
        eval_samples.append(
            SingleTurnSample(
                user_input=s["question"],
                response=s["answer"],
                retrieved_contexts=s["contexts"],
            )
        )

    dataset = EvaluationDataset(samples=eval_samples)

    # Create LLM for evaluation
    ragas_llm = build_ragas_llm()

    logger.info("Running RAGAS evaluation with metrics: %s on %d samples...", metrics_list, len(eval_samples))
    start = time.perf_counter()

    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=ragas_llm,
        show_progress=True,
    )

    elapsed = time.perf_counter() - start
    logger.info("RAGAS evaluation completed in %.1fs", elapsed)

    return {
        "scores": dict(result),
        "elapsed_seconds": elapsed,
        "num_samples": len(eval_samples),
        "metrics": metrics_list,
    }


def push_scores_to_langfuse(langfuse, trace_ids: list[str | None], result: dict, metrics_list: list[str]) -> None:
    """Push per-sample RAGAS scores to Langfuse as evaluation scores on traces."""
    scores = result.get("scores", {})
    if not scores or not langfuse:
        return

    pushed = 0
    for i, trace_id in enumerate(trace_ids):
        if trace_id is None:
            continue
        for metric_name in metrics_list:
            if metric_name in scores:
                # RAGAS returns a single aggregate score; per-sample scores
                # are in the DataFrame if available. Use aggregate as fallback.
                value = scores[metric_name]
                try:
                    langfuse.create_score(
                        trace_id=trace_id,
                        name=metric_name,
                        value=float(value),
                        comment=f"RAGAS {metric_name} (aggregate over {result.get('num_samples', 0)} samples)",
                    )
                    pushed += 1
                except Exception:
                    logger.debug("Failed to push score %s for trace %s", metric_name, trace_id, exc_info=True)

    if pushed > 0:
        langfuse.flush()
        logger.info("Pushed %d RAGAS scores to Langfuse", pushed)


def main():
    parser = argparse.ArgumentParser(description="RAGAS evaluation for Vitreon Legal RAG pipeline")
    parser.add_argument("--corpus", default="difc", help="Corpus to evaluate (default: difc)")
    parser.add_argument("--sample", type=int, default=10, help="Number of questions to sample (default: 10)")
    parser.add_argument(
        "--metrics",
        nargs="+",
        default=["faithfulness", "answer_relevancy"],
        help="RAGAS metrics to run (default: faithfulness answer_relevancy)",
    )
    parser.add_argument("--output", default=None, help="Output JSON file path")
    args = parser.parse_args()

    # Load questions
    questions_path = Path(__file__).parent.parent / "data" / "questions.json"
    if not questions_path.exists():
        logger.error("Questions file not found: %s", questions_path)
        sys.exit(1)

    with open(questions_path) as f:
        questions = json.load(f)

    logger.info("Loaded %d questions from %s", len(questions), questions_path)

    # Initialize Langfuse (optional)
    langfuse = _get_langfuse()
    if langfuse:
        logger.info("Langfuse enabled — traces and scores will be pushed")

    # Collect pipeline outputs
    samples, trace_ids = asyncio.run(collect_samples(questions, args.corpus, args.sample, langfuse))

    if not samples:
        logger.error("No samples collected — cannot run evaluation")
        sys.exit(1)

    logger.info("Collected %d samples, running RAGAS evaluation...", len(samples))

    # Run RAGAS
    result = run_ragas_evaluation(samples, args.metrics)

    # Push scores to Langfuse
    if langfuse and trace_ids:
        push_scores_to_langfuse(langfuse, trace_ids, result, args.metrics)

    # Output
    output_data = {
        "corpus": args.corpus,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **result,
    }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2, default=str)
        logger.info("Results saved to %s", output_path)
    else:
        print(json.dumps(output_data, indent=2, default=str))


if __name__ == "__main__":
    main()
