#!/usr/bin/env python3
"""Build FAISS + BM25 indexes for LegalBench-RAG corpus.

Downloads legal contracts corpus from Dropbox, chunks them with RCTS
(recursive character text splitter), embeds with Snowflake Arctic Embed,
and builds:
  - FAISS index (IndexFlatIP for cosine similarity)
  - BM25 index (bm25s with legal tokenizer)

Usage:
    python benchmarks/legalbench-rag/build_index.py
"""

import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import requests

BENCH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BENCH_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = BENCH_DIR / "data"
CORPUS_DIR = DATA_DIR / "corpus"
INDEX_DIR = DATA_DIR / "index"

DROPBOX_URL = "https://www.dropbox.com/scl/fo/r7xfa5i3hdsbxex1w6amw/AID389Olvtm-ZLTKAPrw6k4?rlkey=5n8zrbk4c08lbit3iiexofmwg&st=0hu354cq&dl=1"

# RCTS chunking parameters (matches paper's best config)
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def download_corpus():
    """Download corpus from Dropbox if not already present."""
    if CORPUS_DIR.exists() and any(CORPUS_DIR.rglob("*.txt")):
        print(f"[build_index] Corpus already exists at {CORPUS_DIR}")
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DATA_DIR / "legalbenchrag_data.zip"

    print("[build_index] Downloading corpus from Dropbox...")
    resp = requests.get(DROPBOX_URL, stream=True, timeout=120)
    resp.raise_for_status()
    with open(zip_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    print("[build_index] Extracting...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(DATA_DIR)
    zip_path.unlink()
    print(f"[build_index] Corpus extracted to {DATA_DIR}")


def chunk_text_rcts(
    text: str, file_path: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[dict]:
    """Recursive Character Text Splitter — chunk text into overlapping segments.

    Returns list of {"file": str, "start": int, "end": int, "text": str}.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))

        # Try to break at paragraph, then sentence, then word boundary
        if end < len(text):
            # Look for paragraph break
            para_break = text.rfind("\n\n", start, end)
            if para_break > start + chunk_size // 2:
                end = para_break + 2
            else:
                # Look for sentence break
                sent_break = max(
                    text.rfind(". ", start, end),
                    text.rfind(".\n", start, end),
                )
                if sent_break > start + chunk_size // 2:
                    end = sent_break + 2
                else:
                    # Look for word break
                    word_break = text.rfind(" ", start, end)
                    if word_break > start + chunk_size // 2:
                        end = word_break + 1

        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(
                {
                    "file": file_path,
                    "start": start,
                    "end": end,
                    "text": chunk_text,
                }
            )

        start = end - overlap if end < len(text) else len(text)

    return chunks


def load_and_chunk_corpus() -> list[dict]:
    """Load all corpus .txt files and chunk them."""
    all_chunks = []

    txt_files = sorted(CORPUS_DIR.rglob("*.txt"))
    print(f"[build_index] Found {len(txt_files)} corpus files")

    for txt_file in txt_files:
        try:
            content = txt_file.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"  Warning: skipping {txt_file}: {e}")
            continue

        rel_path = str(txt_file.relative_to(CORPUS_DIR))
        chunks = chunk_text_rcts(content, rel_path)
        all_chunks.extend(chunks)

    print(f"[build_index] Created {len(all_chunks)} chunks from {len(txt_files)} files")
    return all_chunks


def main():
    import bm25s
    import faiss
    from sentence_transformers import SentenceTransformer

    # Step 1: Download corpus
    download_corpus()

    # Step 2: Chunk corpus
    chunks = load_and_chunk_corpus()
    if not chunks:
        print("[build_index] ERROR: No chunks created. Check corpus directory.")
        sys.exit(1)

    texts = [c["text"] for c in chunks]

    # Step 3: Build FAISS index
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    print("[build_index] Loading embedding model...")
    import torch

    device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(
        "Snowflake/snowflake-arctic-embed-l-v2.0",
        device=device,
        trust_remote_code=True,
    )

    print(f"[build_index] Embedding {len(texts)} chunks on {device}...")
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=True,
        batch_size=16,
    )

    print("[build_index] Building FAISS index...")
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings.astype(np.float32))
    faiss.write_index(index, str(INDEX_DIR / "faiss_index.bin"))

    # Save metadata (file, start, end, text for each chunk)
    metadata = []
    for i, chunk in enumerate(chunks):
        metadata.append(
            {
                "chunk_id": i,
                "file": chunk["file"],
                "start": chunk["start"],
                "end": chunk["end"],
                "text": chunk["text"],
            }
        )
    with open(INDEX_DIR / "faiss_metadata.json", "w") as f:
        json.dump(metadata, f)
    print(f"[build_index] FAISS index saved: {index.ntotal} vectors")

    # Step 4: Build BM25 index
    print("[build_index] Building BM25 index...")
    from arlc.indexing.legal_tokenizer import legal_tokenize_corpus

    tokenized = legal_tokenize_corpus(texts)
    bm25 = bm25s.BM25()
    bm25.index(tokenized)

    bm25_dir = INDEX_DIR / "bm25_cache"
    bm25_dir.mkdir(parents=True, exist_ok=True)
    bm25.save(str(bm25_dir))

    # Save chunk IDs for BM25 result mapping
    chunk_ids = list(range(len(chunks)))
    with open(bm25_dir / "corpus_ids.json", "w") as f:
        json.dump(chunk_ids, f)
    print(f"[build_index] BM25 index saved: {len(chunk_ids)} chunks")

    print("[build_index] Done!")


if __name__ == "__main__":
    main()
