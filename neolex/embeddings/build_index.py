"""Build a FAISS index from document chunks using llama-server embeddings.

Usage:
    # Start llama-server first (port 8088), then:
    EMBEDDING_MODEL=llama-server python3 -m neolex.embeddings.build_index \\
        --corpus data/chunks/ \\
        --output data/faiss_llama-server.bin

The metadata JSON is written alongside the .bin file with the same stem and
a .json extension.

Corpus format: directory of .json files, each a list of chunk dicts with
keys {"text": str, "doc_id": str, "page": int, ...}.
"""
from __future__ import annotations

import argparse
import json
import logging
import pathlib
import re
import sys

import faiss
import numpy as np

from neolex.embeddings.config import EMBEDDING_BACKEND

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 64  # llama-server handles GPU batching internally
MAX_CHUNK_CHARS = 7500  # hard limit to stay within Qwen3-8B's 16384-token context
OVERLAP_CHARS = 200


def _split_oversized_text(
    text: str,
    max_chars: int = MAX_CHUNK_CHARS,
    overlap: int = OVERLAP_CHARS,
    _depth: int = 0,
) -> list[str]:
    """Split text exceeding max_chars at paragraph -> sentence -> newline boundaries.

    Returns a list of text pieces each guaranteed <= max_chars.
    Uses 200-char overlap to preserve context across split boundaries.
    """
    if len(text) <= max_chars:
        return [text]

    # Safety valve: prevent infinite recursion on pathological input
    if _depth > 10:
        return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]

    # Try split strategies in preference order
    split_patterns = [
        r"\n\n",              # paragraph boundary
        r"(?<=\.)\s+",       # sentence boundary
        r"\n",               # newline
    ]

    parts = None
    for pattern in split_patterns:
        candidate = re.split(pattern, text)
        if len(candidate) > 1:
            parts = candidate
            break

    if parts is None:
        # Hard character cut as last resort (no overlap to guarantee termination)
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

    # Recursively handle any still-oversized pieces
    result: list[str] = []
    for chunk in chunks:
        if len(chunk) > max_chars:
            result.extend(_split_oversized_text(chunk, max_chars, overlap, _depth + 1))
        else:
            result.append(chunk)

    return result


def validate_and_split_chunks(chunks: list[dict]) -> list[dict]:
    """Validate chunks before embedding: skip empty, split oversized.

    Returns a new list of chunks ready for embedding. Logs warnings
    for any chunks that were skipped or split.
    """
    result: list[dict] = []
    skipped_empty = 0
    split_count = 0

    for chunk in chunks:
        text = chunk.get("text", "")

        # Skip empty/whitespace-only chunks
        if not text or not text.strip():
            skipped_empty += 1
            continue

        # Split oversized chunks
        if len(text) > MAX_CHUNK_CHARS:
            split_count += 1
            logger.warning(
                "Chunk %s has %d chars (limit %d) — splitting at paragraph/sentence boundaries",
                chunk.get("doc_id", "?"),
                len(text),
                MAX_CHUNK_CHARS,
            )
            sub_texts = _split_oversized_text(text)
            for i, sub_text in enumerate(sub_texts):
                sub_chunk = dict(chunk)  # shallow copy
                sub_chunk["text"] = sub_text
                # Give sub-chunks unique chunk_ids to avoid collisions
                if "chunk_id" in sub_chunk:
                    sub_chunk["chunk_id"] = f"{sub_chunk['chunk_id']}_split{i}"
                result.append(sub_chunk)
        else:
            result.append(chunk)

    if skipped_empty:
        logger.warning("Skipped %d empty/whitespace-only chunks", skipped_empty)
    if split_count:
        logger.warning("Split %d oversized chunks into smaller pieces", split_count)

    logger.info(
        "Chunk validation: %d input -> %d output (%d empty skipped, %d split)",
        len(chunks), len(result), skipped_empty, split_count,
    )
    return result


def load_chunks(corpus_dir: str) -> list[dict]:
    """Load all chunks from a directory of JSON files."""
    chunks: list[dict] = []
    corpus_path = pathlib.Path(corpus_dir)
    json_files = sorted(corpus_path.glob("*.json"))
    if not json_files:
        raise FileNotFoundError(f"No .json files found in {corpus_dir}")
    for jf in json_files:
        data = json.loads(jf.read_text())
        if isinstance(data, list):
            chunks.extend(data)
        elif isinstance(data, dict) and "chunks" in data:
            chunks.extend(data["chunks"])
        else:
            logger.warning("Skipping %s: unrecognised format", jf.name)
    logger.info("Loaded %d chunks from %d files.", len(chunks), len(json_files))
    return chunks


def build_index(corpus_dir: str, output_path: str) -> None:
    """Embed all chunks and write FAISS flat index + metadata JSON."""
    if EMBEDDING_BACKEND != "llama-server":
        logger.error(
            "EMBEDDING_MODEL=%r is not supported. Set EMBEDDING_MODEL=llama-server "
            "and start llama-server before running this script.", EMBEDDING_BACKEND
        )
        sys.exit(1)

    from neolex.embeddings.llama_embedder import LlamaServerEmbedder
    embedder = LlamaServerEmbedder(batch_size=BATCH_SIZE)
    logger.info("Using llama-server backend at %s", embedder.url)

    raw_chunks = load_chunks(corpus_dir)
    chunks = validate_and_split_chunks(raw_chunks)
    texts = [c.get("text", "") for c in chunks]
    logger.info("Embedding %d chunks (batch_size=%d)...", len(texts), BATCH_SIZE)

    all_embeddings: list[np.ndarray] = []
    chunks_skipped = 0
    skip_indices: set[int] = set()  # global indices of chunks to drop from metadata

    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start: start + BATCH_SIZE]
        try:
            embs = embedder.embed_texts(batch)
        except Exception:
            # Batch may exceed context window (e.g. very long legal sections).
            # Fall back to one-at-a-time for this batch — skip individual failures.
            logger.warning("Batch %d failed, retrying individually...", start)
            singles: list[np.ndarray] = []
            for j, t in enumerate(batch):
                global_idx = start + j
                try:
                    singles.append(embedder.embed_texts([t]))
                except Exception as single_exc:
                    # Check for HTTP 400 from llama-server (context too long, etc.)
                    is_http_400 = False
                    if hasattr(single_exc, "response"):
                        is_http_400 = getattr(single_exc.response, "status_code", 0) == 400
                    elif "400" in str(single_exc):
                        is_http_400 = True

                    if is_http_400:
                        logger.warning(
                            "Skipping chunk %d (doc_id=%s, %d chars): llama-server 400 — %s",
                            global_idx,
                            chunks[global_idx].get("doc_id", "?"),
                            len(t),
                            single_exc,
                        )
                        skip_indices.add(global_idx)
                        chunks_skipped += 1
                    else:
                        # Non-400 error — re-raise to fail the job visibly
                        raise
            if singles:
                embs = np.concatenate(singles, axis=0)
            else:
                continue  # entire batch was skipped
        all_embeddings.append(embs)
        if start % 500 == 0 or start == 0:
            logger.info("  %d / %d chunks embedded...", min(start + BATCH_SIZE, len(texts)), len(texts))

    if chunks_skipped:
        logger.warning("Total chunks skipped due to embedding errors: %d", chunks_skipped)
        # Remove skipped chunks from the chunks list so metadata stays aligned
        chunks = [c for i, c in enumerate(chunks) if i not in skip_indices]

    matrix = np.concatenate(all_embeddings, axis=0).astype(np.float32)
    actual_dim = matrix.shape[1]
    logger.info("Embedding matrix: %s (dim=%d)", matrix.shape, actual_dim)

    index = faiss.IndexFlatIP(actual_dim)
    index.add(matrix)
    logger.info("FAISS index: %d vectors", index.ntotal)

    output_path_obj = pathlib.Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(output_path_obj))
    logger.info("FAISS index written to %s", output_path_obj)

    metadata = [
        {
            # Primary field used by retriever (pdf_id and doc_id are the same hash value)
            "doc_id": c.get("doc_id", ""),
            "pdf_id": c.get("doc_id", c.get("pdf_id", "")),
            # chunk_id: use explicit field or fall back to doc_id_page
            "chunk_id": c.get("chunk_id") or (
                f"{c.get('doc_id', '')}_{c.get('page', 1)}_0"
            ),
            "page": int(c.get("page", c.get("metadata", {}).get("page", 1))),
            "source_file": f"{c.get('doc_id', '')}.pdf",
            "text": c.get("text", ""),
            "entities": c.get("entities", ""),
        }
        for c in chunks
    ]
    meta_path = output_path_obj.with_suffix(".json")
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    logger.info("Metadata written to %s", meta_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a FAISS index from document chunks using llama-server embeddings."
    )
    parser.add_argument("--corpus", required=True, help="Directory containing chunk JSON files.")
    parser.add_argument("--output", required=True, help="Output path for the FAISS .bin index file.")
    args = parser.parse_args()
    build_index(args.corpus, args.output)


if __name__ == "__main__":
    main()
