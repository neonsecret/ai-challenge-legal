#!/usr/bin/env python3
"""Index Australian corpus chunks into PostgreSQL (pgvector).

Reads data/corpus/au/chunks.json, computes embeddings via llama-server,
and inserts into the `chunks` table with corpus='au'.

Usage:
    uv run python scripts/index_au_corpus.py
    uv run python scripts/index_au_corpus.py --batch-size 32  # smaller batches
    uv run python scripts/index_au_corpus.py --dry-run         # count chunks only

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
import uuid
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

CHUNKS_FILE = PROJECT_ROOT / "data" / "corpus" / "au" / "chunks.json"
CORPUS = "au"
BATCH_SIZE = 64  # embeddings per HTTP call


def load_chunks() -> list[dict]:
    """Load chunks from JSON file."""
    with open(CHUNKS_FILE) as f:
        return json.load(f)


def get_embedder():
    """Get the llama-server embedder."""
    from neolex.embeddings.llama_embedder import LlamaServerEmbedder

    return LlamaServerEmbedder()


CHECKPOINT_FILE = PROJECT_ROOT / "data" / "corpus" / "au" / ".embed_checkpoint.json"
MAX_RETRIES = 5
RETRY_DELAY = 10  # seconds


def _save_checkpoint(embeddings: list[list[float]], batch_idx: int) -> None:
    """Save embedding progress to disk for resume."""
    CHECKPOINT_FILE.write_text(
        json.dumps(
            {
                "batch_idx": batch_idx,
                "count": len(embeddings),
            }
        )
    )
    # Save embeddings as numpy for efficiency
    np.save(str(CHECKPOINT_FILE.with_suffix(".npy")), np.array(embeddings, dtype=np.float32))


def _load_checkpoint() -> tuple[list[list[float]], int]:
    """Load checkpoint if exists. Returns (embeddings, start_batch_idx)."""
    if CHECKPOINT_FILE.exists() and CHECKPOINT_FILE.with_suffix(".npy").exists():
        meta = json.loads(CHECKPOINT_FILE.read_text())
        embeddings = np.load(str(CHECKPOINT_FILE.with_suffix(".npy"))).tolist()
        logger.info("  Resuming from checkpoint: %d embeddings, batch_idx=%d", len(embeddings), meta["batch_idx"])
        return embeddings, meta["batch_idx"]
    return [], 0


def compute_embeddings(embedder, texts: list[str], batch_size: int = BATCH_SIZE) -> list[list[float]]:
    """Compute embeddings for all texts in batches with retry and resume."""
    all_embeddings, start_idx = _load_checkpoint()
    total = len(texts)

    if start_idx > 0:
        logger.info("  Resuming from batch index %d (%d/%d already done)", start_idx, len(all_embeddings), total)

    for i in range(start_idx, total, batch_size):
        batch = texts[i : i + batch_size]
        batch_end = min(i + batch_size, total)

        for attempt in range(MAX_RETRIES):
            try:
                logger.info("  Embedding batch %d-%d / %d", i + 1, batch_end, total)
                embeddings = embedder.encode(batch, normalize_embeddings=True)
                if isinstance(embeddings, np.ndarray):
                    all_embeddings.extend(embeddings.tolist())
                else:
                    all_embeddings.extend(embeddings)
                break
            except Exception as e:
                logger.warning(
                    "  Batch %d-%d failed (attempt %d/%d): %s", i + 1, batch_end, attempt + 1, MAX_RETRIES, e
                )
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_DELAY * (attempt + 1)
                    logger.info("  Retrying in %ds...", wait)
                    time.sleep(wait)
                else:
                    logger.error(
                        "  Batch %d-%d failed after %d retries, saving checkpoint", i + 1, batch_end, MAX_RETRIES
                    )
                    _save_checkpoint(all_embeddings, i)
                    raise

        # Checkpoint every 500 batches
        if (i // batch_size) % 500 == 0 and i > start_idx:
            _save_checkpoint(all_embeddings, i + batch_size)

    # Clean up checkpoint on success
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
    npy_file = CHECKPOINT_FILE.with_suffix(".npy")
    if npy_file.exists():
        npy_file.unlink()

    return all_embeddings


def insert_chunks(chunks: list[dict], embeddings: list[list[float]]) -> int:
    """Insert chunks with embeddings into PostgreSQL."""
    from sqlalchemy import create_engine
    from sqlalchemy import text as sa_text

    db_url = os.environ.get("DATABASE_URL", "")
    if "+asyncpg" in db_url:
        db_url = db_url.replace("+asyncpg", "")
    engine = create_engine(db_url)

    inserted = 0
    with engine.begin() as conn:
        # Delete existing AU chunks (clean rebuild)
        result = conn.execute(
            sa_text("DELETE FROM chunks WHERE corpus = :corpus"),
            {"corpus": CORPUS},
        )
        logger.info("Deleted %d existing AU chunks", result.rowcount)

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
                if meta.get("title"):
                    extra["title"] = meta["title"]
                if meta.get("section_title"):
                    extra["section_title"] = meta["section_title"]

                conn.execute(
                    sa_text("""
                        INSERT INTO chunks
                            (id, corpus, tenant_id, doc_id, pdf_id, page, chunk_id,
                             source_file, text, embedding, metadata_extra)
                        VALUES
                            (:id, :corpus, :tenant_id, :doc_id, :pdf_id, :page, :chunk_id,
                             :source_file, :text, cast(:embedding as vector), :metadata_extra)
                        ON CONFLICT (chunk_id) DO UPDATE SET
                            text = EXCLUDED.text,
                            embedding = EXCLUDED.embedding,
                            metadata_extra = EXCLUDED.metadata_extra
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "corpus": CORPUS,
                        "tenant_id": None,
                        "doc_id": meta.get("law", chunk["doc_id"]),
                        "pdf_id": meta.get("law", ""),
                        "page": chunk.get("page", 0),
                        "chunk_id": chunk["doc_id"],  # e.g. privacy_act_1988_00042
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
    """Run verification queries on the AU corpus."""
    from sqlalchemy import create_engine
    from sqlalchemy import text as sa_text

    db_url = os.environ.get("DATABASE_URL", "")
    if "+asyncpg" in db_url:
        db_url = db_url.replace("+asyncpg", "")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        # Count
        result = conn.execute(sa_text("SELECT count(*) FROM chunks WHERE corpus = 'au'"))
        count = result.scalar()
        logger.info("AU chunks in PostgreSQL: %d", count)

        # Count by law
        result = conn.execute(
            sa_text("""
            SELECT pdf_id, count(*) as cnt
            FROM chunks WHERE corpus = 'au'
            GROUP BY pdf_id ORDER BY cnt DESC
        """)
        )
        rows = result.fetchall()
        logger.info("Chunks per law:")
        for law, cnt in rows:
            logger.info("  %s: %d", law, cnt)

        # Full-text search test
        result = conn.execute(
            sa_text("""
            SELECT chunk_id,
                   ts_rank(text_search, plainto_tsquery('simple', 'privacy personal information'))
                   AS rank
            FROM chunks
            WHERE corpus = 'au'
              AND text_search @@ plainto_tsquery('simple', 'privacy personal information')
            ORDER BY rank DESC
            LIMIT 5
        """)
        )
        rows = result.fetchall()
        if rows:
            logger.info("FTS test 'privacy personal information':")
            for cid, rank in rows:
                logger.info("  %s: %.4f", cid, rank)
        else:
            logger.warning("FTS test returned no results")

    engine.dispose()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Index AU corpus into PostgreSQL")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--insert-only", action="store_true", help="Skip embedding, load from saved .npy file")
    args = parser.parse_args()

    embeddings_cache = PROJECT_ROOT / "data" / "corpus" / "au" / "embeddings.npy"

    # Load chunks
    logger.info("Loading chunks from %s", CHUNKS_FILE)
    chunks = load_chunks()
    logger.info("Loaded %d chunks", len(chunks))

    if args.dry_run:
        total_chars = sum(len(c["text"]) for c in chunks)
        laws = set(c.get("metadata", {}).get("law", "") for c in chunks)
        print(f"Chunks: {len(chunks)}")
        print(f"Total chars: {total_chars:,}")
        print(f"Laws: {len(laws)}")
        for law in sorted(laws):
            law_chunks = [c for c in chunks if c.get("metadata", {}).get("law") == law]
            print(f"  {law}: {len(law_chunks)} chunks")
        return

    if args.insert_only:
        logger.info("Loading pre-computed embeddings from %s", embeddings_cache)
        embeddings = np.load(str(embeddings_cache)).tolist()
        logger.info("Loaded %d embeddings", len(embeddings))
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

        # Save embeddings to disk for --insert-only reruns
        logger.info("Saving embeddings to %s", embeddings_cache)
        np.save(str(embeddings_cache), np.array(embeddings, dtype=np.float32))

    # Verify dimensions
    dim = len(embeddings[0]) if embeddings else 0
    logger.info("Embedding dimension: %d", dim)

    # Insert into PostgreSQL
    logger.info("Inserting %d chunks into PostgreSQL (corpus='au')...", len(chunks))
    inserted = insert_chunks(chunks, embeddings)
    logger.info("Inserted %d chunks", inserted)

    # Verify
    verify_index()

    logger.info("AU corpus indexing complete!")


if __name__ == "__main__":
    main()
