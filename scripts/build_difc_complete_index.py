#!/usr/bin/env python3
"""Build a FAISS index from the complete DIFC corpus (laws + judgments).

Reads:
    data/difc_complete/laws/*.pdf       — DIFC law PDFs (via PyMuPDF)
    data/difc_complete/judgments/**/*.txt — Court judgment text files

Writes:
    data/faiss_difc_complete.bin   — FAISS IndexFlatIP (dim=4096, Qwen3-8B)
    data/faiss_difc_complete.json  — Chunk metadata (doc_id, page, text, entities, etc.)

Embedding: via llama-server (Qwen3-Embedding-8B Q4_K_M) at RTX 3070 (100.98.171.97:8088).

Usage:
    # Test with 10 docs first:
    python3 scripts/build_difc_complete_index.py --test 10

    # Full build:
    python3 scripts/build_difc_complete_index.py

    # Override embedding server:
    EMBEDDING_URL=http://localhost:8088 python3 scripts/build_difc_complete_index.py
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import faiss
import numpy as np
import pymupdf
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LAWS_DIR = DATA_DIR / "difc_complete" / "laws"
JUDGMENTS_DIR = DATA_DIR / "difc_complete" / "judgments"
OUTPUT_INDEX = DATA_DIR / "faiss_difc_complete.bin"
OUTPUT_META = DATA_DIR / "faiss_difc_complete.json"

# For remote embedding on RTX 3070: EMBEDDING_URL=http://100.98.171.97:8088
EMBEDDING_URL = os.environ.get("EMBEDDING_URL", "http://localhost:8088")
EMBEDDING_DIM = 4096  # Qwen3-Embedding-8B output dimension

MAX_CHUNK_CHARS = 7500  # Stay within Qwen3-8B's 16384-token context
OVERLAP_CHARS = 200
MIN_CHUNK_CHARS = 100
BATCH_SIZE = int(os.environ.get("EMBED_BATCH_SIZE", "8"))  # Texts per embedding request (lower for local Mac)
MAX_RETRIES = 5
RETRY_BACKOFF = 2.0  # Exponential backoff base (seconds)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Entity extraction patterns (reused from indexer.py)
_ENTITY_PATTERNS = [
    re.compile(r'\b((?:CFI|CA|ARB|ENF|SCT|TCD|DEC)[\s\-_]*\d+[\s/\-_]*\d+)\b', re.IGNORECASE),
    re.compile(r'\b(Article\s+\d+(?:\(\w+\))*)\b', re.IGNORECASE),
    re.compile(r'\b((?:DIFC\s+)?Law\s+No\.?\s*\d+(?:\s+of\s+\d+)?)\b', re.IGNORECASE),
    re.compile(r'\b(Regulation\s+No\.?\s*\d+)\b', re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    """A single text chunk ready for embedding."""
    doc_id: str
    doc_type: str  # "law" or "judgment"
    court_division: str  # "" for laws, e.g. "court_of_first_instance" for judgments
    source_file: str
    page: int  # 1-based page for PDFs, 1 for text files (or section number)
    chunk_idx: int  # 0-based within document
    text: str
    entities: str  # pipe-separated entity list


@dataclass
class BuildStats:
    """Aggregate statistics for the build process."""
    total_docs: int = 0
    law_docs: int = 0
    judgment_docs: int = 0
    total_chunks: int = 0
    chunks_skipped_empty: int = 0
    chunks_split: int = 0
    embedding_time_sec: float = 0.0
    embedding_retries: int = 0
    chunks_failed: int = 0


# ---------------------------------------------------------------------------
# Text splitting
# ---------------------------------------------------------------------------

def _split_text_recursive(
    text: str,
    max_chars: int = MAX_CHUNK_CHARS,
    overlap: int = OVERLAP_CHARS,
    _depth: int = 0,
) -> list[str]:
    """Split text at paragraph -> sentence -> newline boundaries.

    Each subsequent chunk starts with `overlap` chars from the end of the
    previous chunk to preserve context across split boundaries.
    """
    if len(text) <= max_chars:
        return [text]

    if _depth > 10:
        return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]

    split_patterns = [
        r"\n\n",          # paragraph boundary
        r"(?<=\.)\s+",    # sentence boundary
        r"\n",            # any newline
    ]

    parts = None
    for pattern in split_patterns:
        candidate = re.split(pattern, text)
        if len(candidate) > 1:
            parts = candidate
            break

    if parts is None:
        return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]

    chunks: list[str] = []
    buffer = ""

    for part in parts:
        candidate = buffer + part
        if len(candidate) > max_chars and buffer:
            chunks.append(buffer.strip())
            tail = buffer[-overlap:] if len(buffer) > overlap else buffer
            buffer = tail + part
        else:
            buffer = candidate

    if buffer.strip():
        chunks.append(buffer.strip())

    result: list[str] = []
    for chunk in chunks:
        if len(chunk) > max_chars:
            result.extend(_split_text_recursive(chunk, max_chars, overlap, _depth + 1))
        else:
            result.append(chunk)

    return result


def extract_entities(text: str) -> str:
    """Extract legal entities from chunk text, returns pipe-separated string."""
    entities: set[str] = set()
    for pattern in _ENTITY_PATTERNS:
        for match in pattern.findall(text):
            entity = re.sub(r'\s+', ' ', match.strip()).lower()
            if entity:
                entities.add(entity)
    return "|".join(sorted(entities))


# ---------------------------------------------------------------------------
# Document readers
# ---------------------------------------------------------------------------

def read_law_pdf(pdf_path: Path) -> list[Chunk]:
    """Extract text from a law PDF and chunk it."""
    doc_id = pdf_path.stem
    doc = pymupdf.open(str(pdf_path))
    chunks: list[Chunk] = []
    chunk_idx = 0

    # Collect all page texts first for context
    page_texts: list[tuple[int, str]] = []
    for page_num in range(len(doc)):
        text = doc[page_num].get_text().strip()
        if text and len(text) >= 50:  # Skip near-empty pages (covers, blanks)
            page_texts.append((page_num + 1, text))  # 1-based page

    doc.close()

    # Build a document-level title from the first page
    first_text = page_texts[0][1] if page_texts else ""
    title_lines = [line.strip() for line in first_text.split("\n") if line.strip()][:5]
    doc_title = " ".join(title_lines)[:200]

    for page_num, text in page_texts:
        # Split page text into chunks
        sub_texts = _split_text_recursive(text)
        for sub in sub_texts:
            if len(sub.strip()) < MIN_CHUNK_CHARS:
                continue
            chunks.append(Chunk(
                doc_id=doc_id,
                doc_type="law",
                court_division="",
                source_file=pdf_path.name,
                page=page_num,
                chunk_idx=chunk_idx,
                text=sub.strip(),
                entities=extract_entities(sub),
            ))
            chunk_idx += 1

    return chunks


def read_judgment_txt(txt_path: Path, court_division: str) -> list[Chunk]:
    """Read a judgment text file and chunk it."""
    doc_id = txt_path.stem
    text = txt_path.read_text(encoding="utf-8", errors="replace")

    if len(text.strip()) < MIN_CHUNK_CHARS:
        return []

    # The text files have a metadata header (lines starting with #)
    # Keep it as context but don't use it as a separate chunk
    lines = text.split("\n")
    header_lines = []
    body_start = 0
    for i, line in enumerate(lines):
        if line.startswith("# ---"):
            body_start = i + 1
            break
        if line.startswith("#"):
            header_lines.append(line.lstrip("# ").strip())

    header = " | ".join(header_lines) if header_lines else ""
    body = "\n".join(lines[body_start:]).strip()

    if not body or len(body) < MIN_CHUNK_CHARS:
        return []

    chunks: list[Chunk] = []
    sub_texts = _split_text_recursive(body)
    for chunk_idx, sub in enumerate(sub_texts):
        if len(sub.strip()) < MIN_CHUNK_CHARS:
            continue

        # Prepend header context to the first chunk
        chunk_text = sub.strip()
        if chunk_idx == 0 and header:
            chunk_text = f"[{header}]\n\n{chunk_text}"

        chunks.append(Chunk(
            doc_id=doc_id,
            doc_type="judgment",
            court_division=court_division,
            source_file=txt_path.name,
            page=1,  # Text files don't have pages
            chunk_idx=chunk_idx,
            text=chunk_text,
            entities=extract_entities(chunk_text),
        ))

    return chunks


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def check_embedding_server(url: str) -> bool:
    """Verify the embedding server is reachable."""
    try:
        r = requests.get(f"{url}/health", timeout=5)
        return r.ok
    except Exception:
        return False


def embed_batch_with_retry(
    texts: list[str],
    url: str,
    stats: BuildStats,
) -> Optional[np.ndarray]:
    """Embed a batch of texts via llama-server with exponential backoff retry.

    Returns (N, dim) float32 array or None if all retries fail.
    """
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.post(
                f"{url}/v1/embeddings",
                json={"input": texts, "encoding_format": "float"},
                timeout=120,
            )
            r.raise_for_status()
            data = r.json()["data"]
            data.sort(key=lambda x: x["index"])
            matrix = np.array([d["embedding"] for d in data], dtype=np.float32)
            # L2 normalize
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms = np.where(norms == 0.0, 1.0, norms)
            return matrix / norms
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 400:
                # Context too long -- try one-at-a-time
                logger.warning("Batch HTTP 400 (likely context overflow), falling back to individual embedding")
                singles: list[np.ndarray] = []
                for t in texts:
                    try:
                        r2 = requests.post(
                            f"{url}/v1/embeddings",
                            json={"input": [t], "encoding_format": "float"},
                            timeout=120,
                        )
                        r2.raise_for_status()
                        d = r2.json()["data"][0]["embedding"]
                        vec = np.array([d], dtype=np.float32)
                        norm = np.linalg.norm(vec, axis=1, keepdims=True)
                        norm = np.where(norm == 0.0, 1.0, norm)
                        singles.append(vec / norm)
                    except Exception as single_err:
                        logger.warning("Skipping chunk (%d chars): %s", len(t), single_err)
                        stats.chunks_failed += 1
                if singles:
                    return np.concatenate(singles, axis=0)
                return None
            else:
                wait = RETRY_BACKOFF ** (attempt + 1)
                logger.warning(
                    "Embedding HTTP %d (attempt %d/%d), retrying in %.1fs",
                    e.response.status_code if e.response else 0,
                    attempt + 1, MAX_RETRIES, wait,
                )
                stats.embedding_retries += 1
                time.sleep(wait)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            wait = RETRY_BACKOFF ** (attempt + 1)
            logger.warning(
                "Connection error (attempt %d/%d): %s — retrying in %.1fs",
                attempt + 1, MAX_RETRIES, e, wait,
            )
            stats.embedding_retries += 1
            time.sleep(wait)
        except Exception as e:
            wait = RETRY_BACKOFF ** (attempt + 1)
            logger.warning(
                "Unexpected error (attempt %d/%d): %s — retrying in %.1fs",
                attempt + 1, MAX_RETRIES, e, wait,
            )
            stats.embedding_retries += 1
            time.sleep(wait)

    logger.error("All %d retry attempts exhausted for batch of %d texts", MAX_RETRIES, len(texts))
    return None


# ---------------------------------------------------------------------------
# Main build pipeline
# ---------------------------------------------------------------------------

def collect_documents(test_limit: int = 0) -> list[Chunk]:
    """Collect all documents and chunk them.

    Args:
        test_limit: If > 0, process only this many documents total.
    """
    all_chunks: list[Chunk] = []
    doc_count = 0

    # Phase 1: Law PDFs
    pdf_files = sorted(LAWS_DIR.glob("*.pdf"))
    logger.info("Found %d law PDFs in %s", len(pdf_files), LAWS_DIR)

    for pdf_path in pdf_files:
        if test_limit and doc_count >= test_limit:
            break
        try:
            chunks = read_law_pdf(pdf_path)
            all_chunks.extend(chunks)
            logger.info("  [LAW] %s: %d chunks", pdf_path.name, len(chunks))
            doc_count += 1
        except Exception as e:
            logger.error("  [LAW FAIL] %s: %s", pdf_path.name, e)

    law_count = doc_count
    logger.info("Laws processed: %d documents, %d chunks", law_count, len(all_chunks))

    # Phase 2: Judgment text files
    court_dirs = sorted(d for d in JUDGMENTS_DIR.iterdir() if d.is_dir())
    logger.info("Found %d court divisions in %s", len(court_dirs), JUDGMENTS_DIR)

    chunks_before_judgments = len(all_chunks)
    for court_dir in court_dirs:
        court_name = court_dir.name
        txt_files = sorted(court_dir.glob("*.txt"))
        court_chunks = 0

        for txt_path in txt_files:
            if test_limit and doc_count >= test_limit:
                break
            try:
                chunks = read_judgment_txt(txt_path, court_name)
                all_chunks.extend(chunks)
                court_chunks += len(chunks)
                doc_count += 1
            except Exception as e:
                logger.error("  [JUDGMENT FAIL] %s: %s", txt_path.name, e)

        logger.info("  [%s] %d docs, %d chunks", court_name, len(txt_files), court_chunks)

        if test_limit and doc_count >= test_limit:
            break

    judgment_count = doc_count - law_count
    judgment_chunks = len(all_chunks) - chunks_before_judgments
    logger.info("Judgments processed: %d documents, %d chunks", judgment_count, judgment_chunks)
    logger.info("Total: %d documents, %d chunks", doc_count, len(all_chunks))

    return all_chunks


def build_index(chunks: list[Chunk], stats: BuildStats) -> None:
    """Embed all chunks and build the FAISS index."""

    # Verify embedding server
    if not check_embedding_server(EMBEDDING_URL):
        logger.error("Embedding server at %s is not reachable", EMBEDDING_URL)
        sys.exit(1)
    logger.info("Embedding server at %s is healthy", EMBEDDING_URL)

    texts = [c.text for c in chunks]

    # Resume support: load checkpoint if exists
    CHECKPOINT_DIR = DATA_DIR / "difc_build_checkpoint"
    CHECKPOINT_EMBEDDINGS = CHECKPOINT_DIR / "embeddings.npy"
    CHECKPOINT_META = CHECKPOINT_DIR / "progress.json"
    resume_from = 0
    all_embeddings: list[np.ndarray] = []

    if CHECKPOINT_EMBEDDINGS.exists() and CHECKPOINT_META.exists():
        cp = json.loads(CHECKPOINT_META.read_text())
        if cp.get("total_chunks") == len(texts):
            resume_from = cp["embedded_count"]
            saved = np.load(str(CHECKPOINT_EMBEDDINGS))
            all_embeddings.append(saved)
            logger.info("Resuming from checkpoint: %d / %d chunks already embedded", resume_from, len(texts))
        else:
            logger.warning("Checkpoint chunk count mismatch (%d vs %d), starting fresh", cp.get("total_chunks"), len(texts))

    if resume_from == 0:
        CHECKPOINT_DIR.mkdir(exist_ok=True)

    logger.info("Embedding %d chunks (batch_size=%d, dim=%d, starting at %d)...", len(texts), BATCH_SIZE, EMBEDDING_DIM, resume_from)

    skip_indices: set[int] = set()
    embed_start = time.monotonic()
    new_embeddings: list[np.ndarray] = []

    for start in range(resume_from, len(texts), BATCH_SIZE):
        batch = texts[start:start + BATCH_SIZE]
        result = embed_batch_with_retry(batch, EMBEDDING_URL, stats)

        if result is not None:
            if result.shape[0] < len(batch):
                for i in range(result.shape[0], len(batch)):
                    skip_indices.add(start + i)
            new_embeddings.append(result)
        else:
            for i in range(len(batch)):
                skip_indices.add(start + i)
            stats.chunks_failed += len(batch)

        processed = min(start + BATCH_SIZE, len(texts))
        if processed % 100 == 0 or processed == len(texts) or start == resume_from:
            elapsed = time.monotonic() - embed_start
            done_this_run = processed - resume_from
            rate = done_this_run / elapsed if elapsed > 0 else 0
            remaining = len(texts) - processed
            eta = remaining / rate if rate > 0 else 0
            logger.info(
                "  %d / %d chunks embedded (%.1f/s, ETA %.0fs)",
                processed, len(texts), rate, eta,
            )

        # Save checkpoint every 500 chunks
        if new_embeddings and (processed - resume_from) % 500 == 0:
            combined = np.concatenate(all_embeddings + new_embeddings, axis=0).astype(np.float32)
            np.save(str(CHECKPOINT_EMBEDDINGS), combined)
            CHECKPOINT_META.write_text(json.dumps({"total_chunks": len(texts), "embedded_count": processed}))
            logger.info("  Checkpoint saved at %d chunks", processed)

    # Merge new embeddings with resumed ones
    if new_embeddings:
        all_embeddings.extend(new_embeddings)

    # Final checkpoint save
    if all_embeddings:
        combined_final = np.concatenate(all_embeddings, axis=0).astype(np.float32)
        CHECKPOINT_DIR.mkdir(exist_ok=True)
        np.save(str(CHECKPOINT_EMBEDDINGS), combined_final)
        CHECKPOINT_META.write_text(json.dumps({"total_chunks": len(texts), "embedded_count": len(texts)}))
        logger.info("Final checkpoint saved")

    stats.embedding_time_sec = time.monotonic() - embed_start

    if not all_embeddings:
        logger.error("No embeddings produced -- cannot build index")
        sys.exit(1)

    matrix = combined_final if 'combined_final' in dir() else np.concatenate(all_embeddings, axis=0).astype(np.float32)
    actual_dim = matrix.shape[1]
    logger.info("Embedding matrix: %s (dim=%d)", matrix.shape, actual_dim)

    if actual_dim != EMBEDDING_DIM:
        logger.warning(
            "Expected dim=%d but got dim=%d -- using actual dimension",
            EMBEDDING_DIM, actual_dim,
        )

    # Filter out failed chunks from metadata
    if skip_indices:
        logger.warning("Removing %d failed chunks from metadata", len(skip_indices))
        chunks = [c for i, c in enumerate(chunks) if i not in skip_indices]

    # Build FAISS index
    index = faiss.IndexFlatIP(actual_dim)
    index.add(matrix)
    logger.info("FAISS index: %d vectors, dim=%d", index.ntotal, actual_dim)

    # Save index
    OUTPUT_INDEX.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(OUTPUT_INDEX))
    logger.info("Index written to %s", OUTPUT_INDEX)

    # Save metadata
    metadata = []
    for c in chunks:
        chunk_id = f"{c.doc_id}_{c.page}_{c.chunk_idx}"
        metadata.append({
            "chunk_id": chunk_id,
            "doc_id": c.doc_id,
            "pdf_id": c.doc_id,  # Compat with existing retriever
            "page": c.page,
            "source_file": c.source_file,
            "text": c.text,
            "entities": c.entities,
            "doc_type": c.doc_type,
            "court_division": c.court_division,
        })

    OUTPUT_META.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    logger.info("Metadata written to %s (%d entries)", OUTPUT_META, len(metadata))


def print_summary(stats: BuildStats, chunks: list[Chunk]) -> None:
    """Print build summary."""
    law_chunks = sum(1 for c in chunks if c.doc_type == "law")
    judgment_chunks = sum(1 for c in chunks if c.doc_type == "judgment")
    total_chars = sum(len(c.text) for c in chunks)
    avg_chars = total_chars // max(len(chunks), 1)

    # Court division breakdown
    divisions: dict[str, int] = {}
    for c in chunks:
        if c.doc_type == "judgment":
            divisions[c.court_division] = divisions.get(c.court_division, 0) + 1

    print("\n" + "=" * 60)
    print("DIFC COMPLETE INDEX BUILD SUMMARY")
    print("=" * 60)
    print(f"\nDocuments:        {stats.total_docs}")
    print(f"  Laws:           {stats.law_docs}")
    print(f"  Judgments:       {stats.judgment_docs}")
    print(f"\nChunks:           {len(chunks)}")
    print(f"  Law chunks:     {law_chunks}")
    print(f"  Judgment chunks: {judgment_chunks}")
    print(f"  Avg chunk size: {avg_chars} chars")
    print(f"  Skipped empty:  {stats.chunks_skipped_empty}")
    print(f"  Split oversized: {stats.chunks_split}")
    print(f"  Failed:         {stats.chunks_failed}")

    if divisions:
        print(f"\nJudgment chunks by division:")
        for div, count in sorted(divisions.items()):
            print(f"  {div}: {count}")

    print(f"\nEmbedding:")
    print(f"  Server:         {EMBEDDING_URL}")
    print(f"  Dimension:      {EMBEDDING_DIM}")
    print(f"  Batch size:     {BATCH_SIZE}")
    print(f"  Time:           {stats.embedding_time_sec:.1f}s")
    rate = len(chunks) / stats.embedding_time_sec if stats.embedding_time_sec > 0 else 0
    print(f"  Rate:           {rate:.1f} chunks/s")
    print(f"  Retries:        {stats.embedding_retries}")

    print(f"\nOutput:")
    print(f"  Index: {OUTPUT_INDEX}")
    print(f"  Meta:  {OUTPUT_META}")

    # Estimate full corpus time if this was a test run
    if stats.total_docs < 100 and rate > 0:
        # Rough estimate: ~4800 docs, ~15 chunks/doc avg
        est_total_chunks = 4800 * 15
        est_time = est_total_chunks / rate
        print(f"\nEstimated full corpus ({est_total_chunks} chunks): {est_time / 60:.0f} minutes")

    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build DIFC complete FAISS index")
    parser.add_argument(
        "--test", type=int, default=0,
        help="Process only this many documents (for testing). 0 = all.",
    )
    parser.add_argument(
        "--chunks-only", action="store_true",
        help="Only chunk documents, don't embed (for debugging chunking).",
    )
    args = parser.parse_args()

    stats = BuildStats()

    # Collect and chunk all documents
    logger.info("=" * 60)
    logger.info("Phase 1: Collecting and chunking documents")
    logger.info("=" * 60)
    chunks = collect_documents(test_limit=args.test)
    stats.total_chunks = len(chunks)

    # Count docs
    law_docs = set()
    judgment_docs = set()
    for c in chunks:
        if c.doc_type == "law":
            law_docs.add(c.doc_id)
        else:
            judgment_docs.add(c.doc_id)
    stats.law_docs = len(law_docs)
    stats.judgment_docs = len(judgment_docs)
    stats.total_docs = stats.law_docs + stats.judgment_docs

    if not chunks:
        logger.error("No chunks produced -- nothing to index")
        sys.exit(1)

    if args.chunks_only:
        logger.info("Chunks-only mode: skipping embedding")
        print_summary(stats, chunks)
        return

    # Embed and build index
    logger.info("=" * 60)
    logger.info("Phase 2: Embedding and building FAISS index")
    logger.info("=" * 60)
    build_index(chunks, stats)

    print_summary(stats, chunks)


if __name__ == "__main__":
    main()
