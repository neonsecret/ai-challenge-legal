#!/usr/bin/env python3
"""Index UK corpus chunks into PostgreSQL (pgvector).

Reads data/corpus/uk/chunks.json, computes embeddings via llama-server,
and inserts into the `chunks` table with corpus='uk'.

Usage:
    uv run python scripts/index_uk_corpus.py
    uv run python scripts/index_uk_corpus.py --batch-size 32  # smaller batches
    uv run python scripts/index_uk_corpus.py --dry-run         # count chunks only

Requires:
    - llama-server running on localhost:8088 (or LLAMA_SERVER_URL)
    - PostgreSQL with chunks table (DATABASE_URL in .env)
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

CHUNKS_FILE = PROJECT_ROOT / "data" / "corpus" / "uk" / "chunks.json"
CORPUS = "uk"
BATCH_SIZE = 64  # embeddings per HTTP call


def load_chunks() -> list[dict]:
    """Load chunks from JSON file."""
    with open(CHUNKS_FILE) as f:
        return json.load(f)


def get_embedder():
    """Get the llama-server embedder."""
    from neolex.embeddings.llama_embedder import LlamaServerEmbedder
    return LlamaServerEmbedder()


def compute_embeddings(embedder, texts: list[str], batch_size: int = BATCH_SIZE) -> list[list[float]]:
    """Compute embeddings for all texts in batches with retry on connection errors."""
    all_embeddings = []
    total = len(texts)
    max_retries = 5

    for i in range(0, total, batch_size):
        batch = texts[i:i + batch_size]
        batch_end = min(i + batch_size, total)
        logger.info("  Embedding batch %d-%d / %d", i + 1, batch_end, total)

        for attempt in range(max_retries):
            try:
                embeddings = embedder.encode(batch, normalize_embeddings=True)
                if isinstance(embeddings, np.ndarray):
                    all_embeddings.extend(embeddings.tolist())
                else:
                    all_embeddings.extend(embeddings)
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 10 * (attempt + 1)
                    logger.warning("  Batch failed (%s), retrying in %ds (attempt %d/%d)",
                                   e, wait, attempt + 1, max_retries)
                    time.sleep(wait)
                else:
                    logger.error("  Batch permanently failed after %d attempts: %s", max_retries, e)
                    raise

    return all_embeddings


def insert_chunks(chunks: list[dict], embeddings: list[list[float]]) -> int:
    """Insert chunks with embeddings into PostgreSQL."""
    from sqlalchemy import create_engine, text as sa_text

    db_url = os.environ.get("DATABASE_URL", "")
    if "+asyncpg" in db_url:
        db_url = db_url.replace("+asyncpg", "")
    engine = create_engine(db_url)

    inserted = 0
    with engine.begin() as conn:
        # Delete existing UK chunks (clean rebuild)
        result = conn.execute(
            sa_text("DELETE FROM chunks WHERE corpus = :corpus"),
            {"corpus": CORPUS},
        )
        logger.info("Deleted %d existing UK chunks", result.rowcount)

        # Insert in batches
        batch_size = 64
        for i in range(0, len(chunks), batch_size):
            batch_end = min(i + batch_size, len(chunks))
            for j in range(i, batch_end):
                chunk = chunks[j]
                emb = embeddings[j]
                vec_str = "[" + ",".join(str(float(x)) for x in emb) + "]"

                # Metadata extra
                extra: dict = {}
                meta = chunk.get("metadata", {})
                if meta.get("display_name"):
                    extra["title"] = meta["display_name"]
                if meta.get("section"):
                    extra["section"] = meta["section"]
                if meta.get("part"):
                    extra["part"] = meta["part"]
                if meta.get("chapter"):
                    extra["chapter"] = meta["chapter"]

                conn.execute(
                    sa_text("""
                        INSERT INTO chunks
                            (id, corpus, tenant_id, doc_id, pdf_id, page, chunk_id,
                             source_file, text, embedding, metadata_extra)
                        VALUES
                            (gen_random_uuid(), :corpus, :tenant_id, :doc_id, :pdf_id, :page, :chunk_id,
                             :source_file, :text, cast(:embedding as vector), :metadata_extra)
                        ON CONFLICT (chunk_id) DO UPDATE SET
                            text = EXCLUDED.text,
                            embedding = EXCLUDED.embedding,
                            metadata_extra = EXCLUDED.metadata_extra
                    """),
                    {
                        "corpus": CORPUS,
                        "tenant_id": None,
                        "doc_id": meta.get("law", chunk["doc_id"]),
                        "pdf_id": meta.get("law", ""),
                        "page": chunk.get("page", 0),
                        "chunk_id": chunk["doc_id"],  # e.g. companies_act_2006_00042
                        "source_file": f"{meta.get('law', '')}.txt",
                        "text": chunk["text"],
                        "embedding": vec_str,
                        "metadata_extra": json.dumps(extra) if extra else None,
                    },
                )

            inserted = batch_end
            logger.info("  Inserted %d / %d chunks", inserted, len(chunks))

    engine.dispose()
    return inserted


def verify_index() -> None:
    """Run verification queries on the UK corpus."""
    from sqlalchemy import create_engine, text as sa_text

    db_url = os.environ.get("DATABASE_URL", "")
    if "+asyncpg" in db_url:
        db_url = db_url.replace("+asyncpg", "")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Count
        result = conn.execute(sa_text(
            "SELECT count(*) FROM chunks WHERE corpus = 'uk'"
        ))
        count = result.scalar()
        logger.info("UK chunks in PostgreSQL: %d", count)

        # Count by law
        result = conn.execute(sa_text("""
            SELECT pdf_id, count(*) as cnt
            FROM chunks WHERE corpus = 'uk'
            GROUP BY pdf_id ORDER BY cnt DESC
        """))
        rows = result.fetchall()
        logger.info("Chunks per law:")
        for law, cnt in rows:
            logger.info("  %s: %d", law, cnt)

        # Full-text search test
        result = conn.execute(sa_text("""
            SELECT chunk_id,
                   ts_rank(text_search, plainto_tsquery('simple', 'employment unfair dismissal'))
                   AS rank
            FROM chunks
            WHERE corpus = 'uk'
              AND text_search @@ plainto_tsquery('simple', 'employment unfair dismissal')
            ORDER BY rank DESC
            LIMIT 5
        """))
        rows = result.fetchall()
        if rows:
            logger.info("FTS test 'employment unfair dismissal':")
            for cid, rank in rows:
                logger.info("  %s: %.4f", cid, rank)
        else:
            logger.warning("FTS test returned no results")

    engine.dispose()


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Index UK corpus into PostgreSQL")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--insert-only", action="store_true",
                       help="Skip embedding, load from cache and insert only")
    args = parser.parse_args()

    CACHE_FILE = PROJECT_ROOT / "data" / "corpus" / "uk" / "embeddings_cache.npy"

    # Load chunks
    logger.info("Loading chunks from %s", CHUNKS_FILE)
    chunks = load_chunks()
    logger.info("Loaded %d chunks", len(chunks))

    if args.dry_run:
        # Show stats
        total_chars = sum(len(c["text"]) for c in chunks)
        laws = set(c.get("metadata", {}).get("law", "") for c in chunks)
        print(f"Chunks: {len(chunks)}")
        print(f"Total chars: {total_chars:,}")
        print(f"Laws: {len(laws)}")
        for law in sorted(laws):
            law_chunks = [c for c in chunks if c.get("metadata", {}).get("law") == law]
            print(f"  {law}: {len(law_chunks)} chunks")
        return

    if args.insert_only and CACHE_FILE.exists():
        # Load cached embeddings
        logger.info("Loading cached embeddings from %s", CACHE_FILE)
        embeddings = np.load(str(CACHE_FILE)).tolist()
        logger.info("Loaded %d cached embeddings (dim=%d)", len(embeddings), len(embeddings[0]))
    else:
        # Compute embeddings
        logger.info("Initializing embedder...")
        embedder = get_embedder()

        texts = [c["text"] for c in chunks]
        logger.info("Computing embeddings for %d chunks (batch_size=%d)...", len(texts), args.batch_size)
        start = time.monotonic()
        embeddings = compute_embeddings(embedder, texts, args.batch_size)
        elapsed = time.monotonic() - start
        logger.info("Embeddings complete in %.1fs (%.1f chunks/sec)", elapsed, len(texts) / elapsed)

        # Cache embeddings to avoid recomputation
        np.save(str(CACHE_FILE), np.array(embeddings))
        logger.info("Cached embeddings to %s", CACHE_FILE)

    # Verify dimensions
    dim = len(embeddings[0]) if embeddings else 0
    logger.info("Embedding dimension: %d", dim)

    # Insert into PostgreSQL
    logger.info("Inserting %d chunks into PostgreSQL (corpus='uk')...", len(chunks))
    inserted = insert_chunks(chunks, embeddings)
    logger.info("Inserted %d chunks", inserted)

    # Verify
    verify_index()

    logger.info("UK corpus indexing complete!")


if __name__ == "__main__":
    main()
