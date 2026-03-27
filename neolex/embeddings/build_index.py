"""Build a FAISS index using Qwen3 embeddings.

Usage:
    EMBEDDING_MODEL=qwen3-8b python3 -m neolex.embeddings.build_index \
        --corpus data/chunks/ \
        --output data/faiss_qwen3_8b.bin

The metadata JSON is written alongside the .bin file with the same stem and
a .json extension.

Corpus format: directory of .json files, each a list of chunk dicts with
keys {"text": str, "doc_id": str, "page": int, ...}.  This matches the
format produced by arlc's indexing pipeline.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import pathlib
import sys

import faiss
import numpy as np

from neolex.embeddings.config import EMBEDDING_BACKEND, EMBEDDING_DIM
from neolex.embeddings.qwen3_embedder import load_qwen3_embedder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 32  # chunks per forward pass


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
    if EMBEDDING_BACKEND == "snowflake":
        logger.error(
            "EMBEDDING_MODEL is 'snowflake' — set EMBEDDING_MODEL=qwen3-8b or qwen3-0.6b "
            "before running this script."
        )
        sys.exit(1)

    chunks = load_chunks(corpus_dir)
    texts = [c.get("text", "") for c in chunks]

    embedder = load_qwen3_embedder(backend=EMBEDDING_BACKEND, dim=EMBEDDING_DIM)

    logger.info(
        "Embedding %d chunks with %s (dim=%d, batch_size=%d)...",
        len(texts),
        EMBEDDING_BACKEND,
        EMBEDDING_DIM,
        BATCH_SIZE,
    )

    all_embeddings: list[np.ndarray] = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]
        embs = embedder.embed_texts(batch)
        all_embeddings.append(embs)
        if (start // BATCH_SIZE) % 10 == 0:
            logger.info(
                "  %d / %d chunks embedded...", min(start + BATCH_SIZE, len(texts)), len(texts)
            )

    matrix = np.concatenate(all_embeddings, axis=0).astype(np.float32)
    logger.info("Embedding matrix shape: %s", matrix.shape)

    # Build flat L2 index (inner-product on normalised vectors == cosine similarity)
    index = faiss.IndexFlatIP(EMBEDDING_DIM)
    index.add(matrix)
    logger.info("FAISS index built: %d vectors.", index.ntotal)

    output_path_obj = pathlib.Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(output_path_obj))
    logger.info("FAISS index written to %s", output_path_obj)

    # Write metadata (doc_id, page) alongside the index
    metadata = [
        {
            "doc_id": c.get("doc_id", ""),
            "page": c.get("page", c.get("metadata", {}).get("page", 1)),
            "text": c.get("text", "")[:200],  # truncated preview
        }
        for c in chunks
    ]
    meta_path = output_path_obj.with_suffix(".json")
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    logger.info("Metadata written to %s", meta_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a FAISS index from document chunks using Qwen3 embeddings."
    )
    parser.add_argument(
        "--corpus",
        required=True,
        help="Directory containing chunk JSON files.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for the FAISS .bin index file.",
    )
    args = parser.parse_args()
    build_index(args.corpus, args.output)


if __name__ == "__main__":
    main()
