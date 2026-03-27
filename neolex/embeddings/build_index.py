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

    chunks = load_chunks(corpus_dir)
    texts = [c.get("text", "") for c in chunks]
    logger.info("Embedding %d chunks (batch_size=%d)...", len(texts), BATCH_SIZE)

    all_embeddings: list[np.ndarray] = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start: start + BATCH_SIZE]
        embs = embedder.embed_texts(batch)
        all_embeddings.append(embs)
        if start % 500 == 0 or start == 0:
            logger.info("  %d / %d chunks embedded...", min(start + BATCH_SIZE, len(texts)), len(texts))

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
            "doc_id": c.get("doc_id", ""),
            "page": c.get("page", c.get("metadata", {}).get("page", 1)),
            "text": c.get("text", "")[:200],
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
