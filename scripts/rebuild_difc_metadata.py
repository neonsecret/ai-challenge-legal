"""Rebuild DIFC FAISS metadata with full chunk text from source PDFs.

The FAISS vectors are fine (embedded from full text). Only the metadata
JSON has truncated text — 100% of 26,947 entries are <= 200 chars,
containing just the SAC header prefix with no actual legal content.

This script:
1. Reads each source PDF
2. Re-chunks pages using the SAME algorithm as arlc/indexing/indexer.py
3. Matches chunks back to metadata entries via chunk_id (doc_id_page_chunkIdx)
4. Preserves the [DOCUMENT: ...] header prefix from the original metadata
5. Replaces the truncated text with header + full chunk text

The FAISS binary (data/faiss_llama-server.bin) stays untouched — it was
built from full text embeddings which are correct.

Usage:
    python3 scripts/rebuild_difc_metadata.py
"""
from __future__ import annotations

import json
import os
import re
import sys

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf  # type: ignore[no-redef]

DOCS_DIR = "data/documents"
META_PATH = "data/faiss_llama-server.json"
BACKUP_PATH = "data/faiss_llama-server.json.bak"

# --- Chunking algorithm copied from arlc/indexing/indexer.py ---
# Must match exactly to produce the same chunk_idx values.

_LEGAL_HEADER_PATTERN = re.compile(
    r"(?=\n(?:Article|Section|Part|Schedule|Appendix|Chapter)\s+[\dIVXivx]+)",
    re.IGNORECASE,
)


def split_page_into_chunks(
    text: str, page_num: int, max_chars: int = 500, overlap_chars: int = 0
) -> list[dict]:
    """Split a page's text into paragraph-grouped chunks.

    This is a verbatim copy of arlc.indexing.indexer.split_page_into_chunks
    so that chunk indices match the original index build.
    """
    if len(text) < 500:
        return [{"page": page_num, "text": text, "chunk_idx": 0}]

    header_splits = _LEGAL_HEADER_PATTERN.split(text)
    if len(header_splits) >= 2:
        paragraphs = [s.strip() for s in header_splits if s.strip()]
    else:
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = (current + "\n\n" + para).strip() if current else para
        else:
            if current:
                chunks.append(current)
                current = ""

            if len(para) > max_chars:
                sentences = re.split(r"(?<=[.!?])\s+", para)

                if len(sentences) == 1:
                    sentences = [
                        s.strip() + ";" if i < len(para.split(";")) - 1 else s.strip()
                        for i, s in enumerate(para.split(";"))
                        if s.strip()
                    ]

                if len(sentences) == 1 and len(sentences[0]) > max_chars:
                    txt = sentences[0]
                    while txt:
                        chunk_size = max_chars if len(txt) > max_chars else len(txt)
                        chunks.append(txt[:chunk_size])
                        txt = txt[chunk_size:]
                else:
                    for sent in sentences:
                        if len(current) + len(sent) + 1 <= max_chars:
                            current = (
                                (current + " " + sent).strip() if current else sent
                            )
                        else:
                            if current:
                                chunks.append(current)
                            if len(sent) > max_chars:
                                txt = sent
                                while txt:
                                    chunk_size = (
                                        max_chars
                                        if len(txt) > max_chars
                                        else len(txt)
                                    )
                                    chunks.append(txt[:chunk_size])
                                    txt = txt[chunk_size:]
                                current = ""
                            else:
                                current = sent
            else:
                current = (
                    para
                    if overlap_chars == 0
                    else current[-overlap_chars:].lstrip() + "\n\n" + para
                )

    if current:
        chunks.append(current)

    if not chunks:
        return [{"page": page_num, "text": text, "chunk_idx": 0}]

    return [{"page": page_num, "text": c, "chunk_idx": i} for i, c in enumerate(chunks)]


# --- Oversized splitting from neolex/embeddings/build_index.py ---
# The llama-server index build also applied this splitting step.

MAX_CHUNK_CHARS = 7500
OVERLAP_CHARS = 200


def _split_oversized_text(
    text: str,
    max_chars: int = MAX_CHUNK_CHARS,
    overlap: int = OVERLAP_CHARS,
    _depth: int = 0,
) -> list[str]:
    """Split text exceeding max_chars at paragraph -> sentence -> newline boundaries."""
    if len(text) <= max_chars:
        return [text]

    if _depth > 10:
        return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]

    split_patterns = [
        r"\n\n",
        r"(?<=\.)\s+",
        r"\n",
    ]

    parts = None
    for pattern in split_patterns:
        candidate = re.split(pattern, text)
        if len(candidate) > 1:
            parts = candidate
            break

    if parts is None:
        return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]

    chunks: list[str] = []
    buffer = ""

    for part in parts:
        candidate_buf = buffer + part
        if len(candidate_buf) > max_chars and buffer:
            chunks.append(buffer.strip())
            tail = buffer[-overlap:] if len(buffer) > overlap else buffer
            buffer = tail + part
        else:
            buffer = candidate_buf

    if buffer.strip():
        chunks.append(buffer.strip())

    result: list[str] = []
    for chunk in chunks:
        if len(chunk) > max_chars:
            result.extend(
                _split_oversized_text(chunk, max_chars, overlap, _depth + 1)
            )
        else:
            result.append(chunk)

    return result


def extract_and_chunk_pdf(pdf_path: str) -> dict[str, str]:
    """Extract text from PDF and chunk it, returning {chunk_id: chunk_text}.

    Applies the same two-stage chunking pipeline as the original index build:
    1. split_page_into_chunks (from arlc/indexing/indexer.py)
    2. _split_oversized_text (from neolex/embeddings/build_index.py)
    """
    pdf_id = os.path.basename(pdf_path).replace(".pdf", "")
    doc = pymupdf.open(pdf_path)
    result: dict[str, str] = {}

    for page_num in range(len(doc)):
        text = doc[page_num].get_text().strip()
        if not text:
            continue

        # Stage 1: page-level chunking (same as indexer.py)
        page_chunks = split_page_into_chunks(text, page_num + 1)  # 1-based

        for chunk_info in page_chunks:
            chunk_text = chunk_info["text"]
            page = chunk_info["page"]
            chunk_idx = chunk_info["chunk_idx"]

            # Stage 2: oversized splitting (same as build_index.py)
            if len(chunk_text) > MAX_CHUNK_CHARS:
                sub_texts = _split_oversized_text(chunk_text)
                for i, sub_text in enumerate(sub_texts):
                    cid = f"{pdf_id}_{page}_{chunk_idx}_split{i}"
                    result[cid] = sub_text
            else:
                cid = f"{pdf_id}_{page}_{chunk_idx}"
                result[cid] = chunk_text

    doc.close()
    return result


def extract_header(old_text: str) -> str:
    """Extract the [DOCUMENT: ...] header prefix from truncated text."""
    if not old_text.startswith("[DOCUMENT:"):
        return ""
    bracket_end = old_text.find("]")
    if bracket_end > 0:
        return old_text[: bracket_end + 1] + "\n\n"
    return ""


def main() -> None:
    # Load current metadata
    with open(META_PATH) as f:
        meta = json.load(f)
    print(f"Loaded {len(meta)} chunks from {META_PATH}")

    # Backup
    with open(BACKUP_PATH, "w") as f:
        json.dump(meta, f)
    print(f"Backed up to {BACKUP_PATH}")

    # Stats before
    truncated = sum(1 for m in meta if len(m.get("text", "")) <= 200)
    avg_len = sum(len(m.get("text", "")) for m in meta) // len(meta)
    print(f"Before: {truncated} truncated ({truncated * 100 / len(meta):.1f}%), avg length: {avg_len}")

    # Group metadata entries by source PDF
    by_pdf: dict[str, list[int]] = {}
    for i, m in enumerate(meta):
        pdf_name = m.get("source_file", "")
        if not pdf_name:
            pdf_name = m.get("pdf_id", "") + ".pdf"
        if pdf_name not in by_pdf:
            by_pdf[pdf_name] = []
        by_pdf[pdf_name].append(i)

    print(f"Processing {len(by_pdf)} PDFs...")

    updated = 0
    matched_by_rechunk = 0
    matched_by_page_fallback = 0
    missing_pdfs = 0
    unmatched = 0

    for pdf_idx, (pdf_name, indices) in enumerate(sorted(by_pdf.items())):
        pdf_path = os.path.join(DOCS_DIR, pdf_name)
        if not os.path.exists(pdf_path):
            print(f"  Missing PDF: {pdf_name} ({len(indices)} chunks)", file=sys.stderr)
            missing_pdfs += len(indices)
            continue

        # Re-chunk using the same algorithm
        chunk_map = extract_and_chunk_pdf(pdf_path)

        # Also build a page->full_text fallback map
        doc = pymupdf.open(pdf_path)
        page_text_map: dict[int, str] = {}
        for page_num in range(len(doc)):
            text = doc[page_num].get_text().strip()
            if text:
                page_text_map[page_num + 1] = text  # 1-based
        doc.close()

        for idx in indices:
            chunk_id = meta[idx].get("chunk_id", "")
            header = extract_header(meta[idx].get("text", ""))

            # Try exact chunk_id match first
            if chunk_id in chunk_map:
                full_text = chunk_map[chunk_id]
                meta[idx]["text"] = header + full_text
                updated += 1
                matched_by_rechunk += 1
                continue

            # Fallback: use full page text if chunk_id doesn't match
            page = meta[idx].get("page", 1)
            if page in page_text_map:
                full_text = page_text_map[page]
                meta[idx]["text"] = header + full_text
                updated += 1
                matched_by_page_fallback += 1
                continue

            unmatched += 1

        if (pdf_idx + 1) % 50 == 0:
            print(f"  {pdf_idx + 1}/{len(by_pdf)} PDFs processed...")

    print(f"\nResults:")
    print(f"  Updated:              {updated}")
    print(f"    - by rechunk match: {matched_by_rechunk}")
    print(f"    - by page fallback: {matched_by_page_fallback}")
    print(f"  Missing PDFs:         {missing_pdfs}")
    print(f"  Unmatched:            {unmatched}")
    print(f"  Unchanged:            {len(meta) - updated - missing_pdfs - unmatched}")

    # Stats after
    new_truncated = sum(1 for m in meta if len(m.get("text", "")) <= 200)
    new_avg_len = sum(len(m.get("text", "")) for m in meta) // len(meta)
    max_len = max(len(m.get("text", "")) for m in meta)
    print(f"\nAfter: {new_truncated} truncated ({new_truncated * 100 / len(meta):.1f}%), avg length: {new_avg_len}, max: {max_len}")

    # Save
    with open(META_PATH, "w") as f:
        json.dump(meta, f, ensure_ascii=False)
    print(f"Saved to {META_PATH}")


if __name__ == "__main__":
    main()
