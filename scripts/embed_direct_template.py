#!/usr/bin/env python3
"""Self-contained embedding script for running directly on a GPU server.

This script is designed to be copied to a remote GPU server and run there,
with no dependency on the ai-challenge-legal project.  It talks directly to
llama-server (HTTP) and PostgreSQL (psycopg2), embedding rows that have a
NULL embedding column.

When to use this vs embed_court_decisions.py
--------------------------------------------
- **embed_court_decisions.py** — runs from the project checkout, uses the
  project's ORM / retriever / DB layer.  Good for local runs or CI.
- **This script** — zero project dependencies, self-contained.  Deploy it to
  any GPU server, point it at a DB (via reverse SSH tunnel or direct), and go.

Embedding approach
------------------
- Uses **raw text, no instruction prefix** → document subspace.
  (Qwen3-Embedding is asymmetric: queries get a prefix, documents do NOT.)
- L2 normalisation is done by llama-server (``--embedding --pooling last``
  normalises by default) and verified/enforced client-side.
- Vectors are stored as ``float[]`` in PostgreSQL.

Server setup
------------
Start llama-server with ``--embedding --pooling last``::

    llama-server -m Qwen3-Embedding-8B-Q8_0.gguf --embedding --pooling last \\
        -c 131072 -np 4 -ub 4096 -ngl 99

DB access via reverse SSH tunnel
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
From your laptop (where PostgreSQL runs)::

    ssh -R 15432:localhost:5432 user@gpu-server

Then on the GPU server, use ``--db-url postgresql://user:pass@127.0.0.1:15432/dbname``.

Checkpoint safety
-----------------
The script only fetches rows WHERE the embedding column IS NULL, so it is safe
to interrupt and resume at any time.

Usage
-----
::

    python embed_direct_template.py \\
        --db-url "postgresql://user:pass@127.0.0.1:15432/vitreon_legal" \\
        --table court_decisions \\
        --id-column ecli \\
        --text-column legal_thesis \\
        --embedding-column embedding

    # Multiple text columns (fallback chain: first non-empty wins)
    python embed_direct_template.py \\
        --db-url "..." \\
        --text-column legal_thesis full_text \\
        --batch-size 50 --concurrency 8 --max-errors 20

    # Dry run
    python embed_direct_template.py --db-url "..." --dry-run
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import psycopg2
import psycopg2.extras
import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding via llama-server
# ---------------------------------------------------------------------------

def embed_one(text: str, llama_url: str, timeout: int = 120) -> list[float]:
    """Embed a single text via llama-server /v1/embeddings (no prefix = document subspace).

    Returns an L2-normalised float list.
    """
    resp = requests.post(
        f"{llama_url}/v1/embeddings",
        json={"input": text},
        timeout=timeout,
    )
    resp.raise_for_status()
    vec = resp.json()["data"][0]["embedding"]
    # Enforce L2 normalisation client-side (llama-server should already do it)
    arr = np.array(vec, dtype=np.float32)
    norm = np.linalg.norm(arr)
    if norm > 0 and not math.isclose(norm, 1.0, rel_tol=1e-3):
        arr = arr / norm
    return arr.tolist()


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def fetch_unembedded(conn, table: str, id_col: str, text_cols: list[str],
                     emb_col: str, limit: int) -> list[dict]:
    """Fetch rows where the embedding column IS NULL."""
    cols = ", ".join([id_col] + text_cols)
    query = f"SELECT {cols} FROM {table} WHERE {emb_col} IS NULL LIMIT %s"
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, (limit,))
        return cur.fetchall()


def update_embedding(conn, table: str, id_col: str, emb_col: str,
                     row_id, embedding: list[float]) -> None:
    """Write the embedding vector back to the row."""
    query = f"UPDATE {table} SET {emb_col} = %s WHERE {id_col} = %s"
    with conn.cursor() as cur:
        cur.execute(query, (embedding, row_id))
    conn.commit()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> None:
    conn = psycopg2.connect(args.db_url)
    logger.info("Connected to database")

    total_success = 0
    total_errors = 0
    consecutive_errors = 0

    while True:
        remaining = args.limit - total_success if args.limit else None
        fetch_n = min(args.batch_size, remaining) if remaining else args.batch_size
        if fetch_n <= 0:
            break

        rows = fetch_unembedded(
            conn, args.table, args.id_column, args.text_column,
            args.embedding_column, fetch_n,
        )
        if not rows:
            logger.info("No more unembedded rows — done")
            break

        def process_row(row: dict) -> tuple[str, list[float] | None]:
            """Extract text and embed. Returns (id, embedding_or_None)."""
            row_id = row[args.id_column]
            # Fallback chain: first non-empty text column wins
            text = None
            for col in args.text_column:
                val = row.get(col)
                if val and val.strip():
                    text = val.strip()
                    break
            if not text:
                return row_id, None
            vec = embed_one(text, args.llama_url)
            return row_id, vec

        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = {pool.submit(process_row, row): row for row in rows}
            for fut in as_completed(futures):
                try:
                    row_id, vec = fut.result()
                    if vec is None:
                        total_errors += 1
                        continue
                    if not args.dry_run:
                        update_embedding(
                            conn, args.table, args.id_column,
                            args.embedding_column, row_id, vec,
                        )
                    total_success += 1
                    consecutive_errors = 0
                except Exception as exc:
                    row = futures[fut]
                    logger.warning("Failed %s: %s", row.get(args.id_column, "?"), exc)
                    total_errors += 1
                    consecutive_errors += 1
                    if consecutive_errors >= args.max_errors:
                        logger.error(
                            "Bailing out after %d consecutive errors", args.max_errors
                        )
                        conn.close()
                        sys.exit(1)

        logger.info(
            "Progress: %d embedded, %d errors%s",
            total_success, total_errors,
            " (DRY RUN)" if args.dry_run else "",
        )

        if len(rows) < fetch_n:
            break

    conn.close()
    logger.info(
        "Complete: %d embedded, %d errors%s",
        total_success, total_errors,
        " (DRY RUN — no writes)" if args.dry_run else "",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Self-contained GPU embedding script for llama-server + PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db-url", required=True,
                        help="PostgreSQL connection string")
    parser.add_argument("--llama-url", default="http://localhost:8088",
                        help="llama-server base URL (default: http://localhost:8088)")
    parser.add_argument("--table", default="court_decisions",
                        help="Table name (default: court_decisions)")
    parser.add_argument("--id-column", default="ecli",
                        help="Primary key column (default: ecli)")
    parser.add_argument("--text-column", nargs="+", default=["legal_thesis", "full_text"],
                        help="Text column(s) to embed, in fallback order (default: legal_thesis full_text)")
    parser.add_argument("--embedding-column", default="embedding",
                        help="Column to store the vector (default: embedding)")
    parser.add_argument("--batch-size", type=int, default=50,
                        help="Rows to fetch per DB query (default: 50)")
    parser.add_argument("--concurrency", type=int, default=4,
                        help="Concurrent embed requests (default: 4)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max rows to embed (default: all)")
    parser.add_argument("--max-errors", type=int, default=10,
                        help="Bail after N consecutive errors (default: 10)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute embeddings but skip DB writes")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    run(args)


if __name__ == "__main__":
    main()
