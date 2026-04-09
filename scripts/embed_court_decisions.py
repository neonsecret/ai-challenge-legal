"""Batch embed Czech court decisions using Qwen3-Embedding-8B via llama-server.

Finds rows in court_decisions where embedding IS NULL, embeds each document
using arlc.retriever.embed_document (document subspace, NO instruction prefix),
and stores the L2-normalised vector back via upsert_decision.

Uses embed_document — NOT embed_query. Qwen3 is asymmetric: queries get an
instruction prefix, documents do not.

Run:
    uv run python scripts/embed_court_decisions.py
    uv run python scripts/embed_court_decisions.py --batch-size 100 --concurrency 8
    uv run python scripts/embed_court_decisions.py --dry-run  # count only, no writes
    uv run python scripts/embed_court_decisions.py --limit 500  # embed at most N rows

The script is checkpoint-safe: if interrupted, re-running resumes from where it
left off (WHERE embedding IS NULL filters already-embedded rows).

llama-server URLs (from environment variables, same as the retriever):
    LLAMA_SERVER_URL        Primary (default: http://localhost:8088 = local Mac)
    LLAMA_SERVER_REMOTE_URL Optional remote RTX 3070 (http://100.98.171.97:8088)

The script uses the same LlamaServerEmbedder as the retriever — no duplication.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Allow running as a script from the repo root
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger(__name__)

_LOG_INTERVAL = 100  # log progress every N rows


async def _embed_batch(
    decisions: list,
    semaphore: asyncio.Semaphore,
    dry_run: bool,
) -> tuple[int, int]:
    """Embed a batch of CourtDecision objects and upsert embeddings.

    Returns (success_count, error_count).
    """
    from arlc.retriever import embed_document
    from neolex.db.court_decisions import upsert_decision

    success = 0
    errors = 0

    async def _process_one(decision) -> bool:
        async with semaphore:
            # Prefer legal_thesis (short, dense); fall back to full_text (no truncation).
            # Use embed_document (not embed_query) — documents must be in the
            # document subspace, not the query subspace (Qwen3 is asymmetric).
            thesis = decision.legal_thesis
            ft = decision.full_text
            text = (thesis.strip() if thesis and thesis.strip()
                    else ft.strip() if ft and ft.strip()
                    else None)
            if not text:
                return False
            try:
                # embed_document is synchronous HTTP — run in thread pool
                embedding = await asyncio.to_thread(embed_document, text)
                if not dry_run:
                    await upsert_decision(
                        {
                            "ecli": decision.ecli,
                            "case_number": decision.case_number,
                            "embedding": embedding,
                        }
                    )
                return True
            except Exception as exc:
                logger.warning(
                    "[embed] failed for %s: %s", decision.case_number, exc
                )
                return False

    results = await asyncio.gather(*[_process_one(d) for d in decisions], return_exceptions=True)
    for r in results:
        if r is True:
            success += 1
        else:
            errors += 1

    return success, errors


async def run_embed(
    batch_size: int = 50,
    concurrency: int = 10,
    limit: int | None = None,
    dry_run: bool = False,
) -> None:
    """Main embedding loop.

    Fetches unembedded decisions in batches of ``batch_size``, embeds them
    concurrently with up to ``concurrency`` in-flight requests, logs progress
    every ``_LOG_INTERVAL`` rows.

    Parameters
    ----------
    batch_size : int
        Rows to fetch per DB query (not the embedding concurrency).
    concurrency : int
        Max concurrent embed_query HTTP calls to llama-server.
    limit : int | None
        Stop after embedding at most this many rows.
    dry_run : bool
        If True, compute embeddings but do NOT write them to DB.
    """
    from neolex.db.court_decisions import get_decisions_count, get_unembedded_decisions
    from neolex.db.postgres import init_db

    await init_db()

    total_count = await get_decisions_count()
    logger.info("[embed] total decisions in DB: %d", total_count)

    semaphore = asyncio.Semaphore(concurrency)
    total_processed = 0
    total_success = 0
    total_errors = 0

    while True:
        fetch_n = batch_size if limit is None else min(batch_size, limit - total_processed)
        if fetch_n <= 0:
            break

        batch = await get_unembedded_decisions(limit=fetch_n)
        if not batch:
            logger.info("[embed] no more unembedded decisions — done")
            break

        success, errors = await _embed_batch(batch, semaphore, dry_run=dry_run)
        total_processed += len(batch)
        total_success += success
        total_errors += errors

        if total_processed % _LOG_INTERVAL < batch_size or len(batch) < batch_size:
            logger.info(
                "[embed] progress: %d processed, %d success, %d errors",
                total_processed,
                total_success,
                total_errors,
            )

        if len(batch) < fetch_n:
            # Last batch — fetched fewer than requested, no more rows
            break

        if limit is not None and total_processed >= limit:
            break

    logger.info(
        "[embed] complete: %d processed, %d embedded, %d errors%s",
        total_processed,
        total_success,
        total_errors,
        " (DRY RUN — no writes)" if dry_run else "",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Batch embed court decision legal theses using Qwen3-8B",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Embed all unembedded decisions (checkpoint-safe, can interrupt and resume)
  uv run python scripts/embed_court_decisions.py

  # Faster with high concurrency (RTX 3070 handles 10+ concurrent requests)
  uv run python scripts/embed_court_decisions.py --concurrency 10 --batch-size 100

  # Dry run: count unembedded rows without writing
  uv run python scripts/embed_court_decisions.py --dry-run

  # Embed at most 1000 rows (useful for testing)
  uv run python scripts/embed_court_decisions.py --limit 1000
""",
    )
    parser.add_argument("--batch-size", type=int, default=50, help="DB fetch batch size (default: 50)")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent embed calls (default: 10)")
    parser.add_argument("--limit", type=int, default=None, help="Max rows to embed (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Compute embeddings but skip DB writes")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    asyncio.run(
        run_embed(
            batch_size=args.batch_size,
            concurrency=args.concurrency,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
