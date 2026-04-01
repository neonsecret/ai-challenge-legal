#!/usr/bin/env python3
"""Chunk Czech law text files into section-aware passages.

Strategy:
  - Split on § (section) boundaries — never split mid-paragraph
  - If a § is under ~1000 tokens (~4000 chars), keep it whole
  - If a § is over ~1000 tokens, split at odstavec (paragraph) boundaries within it
  - Each chunk includes the full § header and structural context

Reads .txt files from data/corpus/czech/ and writes:
    data/corpus/czech/chunks.json  — list of chunk dicts

Each chunk:
    {
        "doc_id": "<law_short_name>_<5-digit-idx>",
        "page": <section_number>,
        "text": "[law_name] PART > HEAD > DIV\n§ 51\n(1) ...",
        "metadata": { "law": "...", "section": "§ 51", "part": "..." }
    }

Usage:
    python3 scripts/chunk_czech_corpus.py
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

INPUT_DIR = Path("data/corpus/czech")
OUTPUT_FILE = Path("data/corpus/czech/chunks.json")

# Hard limit: 7500 chars guarantees we stay within Qwen3-8B's 16384-token
# context window (~2 chars/token for Czech diacritics).
MAX_SECTION_CHARS = 7500
MIN_CHUNK_CHARS = 100
OVERLAP_CHARS = 200


def _section_to_num(sec: str) -> int:
    m = re.search(r"(\d+)", sec)
    return int(m.group(1)) if m else 0


def _split_into_sections(text: str) -> list[dict]:
    """Split law text into raw sections at § boundaries."""
    lines = text.splitlines()
    sections: list[dict] = []

    current_part = ""
    current_head = ""
    current_div = ""
    current_section = ""
    current_lines: list[str] = []

    para_re = re.compile(r"^§\s*(\d+[a-z]?)")

    def flush():
        if current_lines:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append(
                    {
                        "section": current_section,
                        "part": current_part,
                        "head": current_head,
                        "div": current_div,
                        "body": body,
                    }
                )

    for line in lines:
        stripped = line.strip()

        # Track structural headers
        if stripped.startswith("ČÁST") or stripped.startswith("část"):
            current_part = stripped
            current_head = ""
            current_div = ""
        elif stripped.startswith("HLAVA") or stripped.startswith("Hlava"):
            current_head = stripped
            current_div = ""
        elif re.match(r"^Díl\s+\d+", stripped, re.IGNORECASE):
            current_div = stripped

        # New § starts a new section
        if para_re.match(stripped):
            flush()
            current_section = stripped.split("\n")[0]  # just the § line
            current_lines = [stripped]
        elif stripped:
            current_lines.append(stripped)
        else:
            current_lines.append("")

    flush()
    return sections


def _split_text_recursive(
    text: str,
    max_chars: int = MAX_SECTION_CHARS,
    overlap: int = OVERLAP_CHARS,
    header: str = "",
    _depth: int = 0,
) -> list[str]:
    """Recursively split text so every piece is <= max_chars.

    Strategy (tried in order):
      1. Paragraph boundaries: ``\\n\\(\\d+\\)`` (Czech odstavec markers)
      2. Sentence boundaries: ``. `` or ``.\\n``
      3. Newline boundaries: ``\\n``
      4. Hard character cut (last resort, no overlap)

    Each subsequent chunk starts with *overlap* chars from the end of the
    previous chunk so context is preserved across boundaries.
    """
    if len(text) <= max_chars:
        return [text]

    # Safety valve: if we recurse too deeply, force hard split with no overlap
    if _depth > 10:
        return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]

    # Try split strategies in order of preference
    split_patterns = [
        r"(?=\n\(\d+\))",  # odstavec marker (paragraph)
        r"(?<=\.)\s+",  # sentence boundary
        r"\n",  # any newline
    ]

    parts = None
    for pattern in split_patterns:
        candidate = re.split(pattern, text)
        if len(candidate) > 1:
            parts = candidate
            break

    if parts is None:
        # Last resort: hard character split with NO overlap to guarantee termination
        return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]

    # Greedily accumulate parts into chunks that fit within the limit
    chunks: list[str] = []
    buffer = ""

    for part in parts:
        candidate = buffer + part
        if len(candidate) > max_chars and buffer:
            chunks.append(buffer.strip())
            # Overlap: carry tail of previous chunk into the next one
            tail = buffer[-overlap:] if len(buffer) > overlap else buffer
            buffer = tail + part
        else:
            buffer = candidate

    if buffer.strip():
        chunks.append(buffer.strip())

    # Recursively split any chunk that is still over the limit
    result: list[str] = []
    for chunk in chunks:
        if len(chunk) > max_chars:
            result.extend(_split_text_recursive(chunk, max_chars, overlap, header, _depth + 1))
        else:
            result.append(chunk)

    return result


def chunk_law_text(text: str, law_name: str) -> list[dict]:
    """Split law text into section-aware chunks."""
    raw_sections = _split_into_sections(text)
    chunks: list[dict] = []
    chunk_idx = 0

    for section in raw_sections:
        # Build context header
        header_parts = [p for p in [section["part"], section["head"], section["div"]] if p]
        context = " > ".join(header_parts) if header_parts else ""

        body = section["body"]

        # Build the prefix that will be prepended to every chunk
        if context:
            prefix = f"[{law_name}] {context}\n"
        else:
            prefix = f"[{law_name}]\n"

        # Continuation header for split chunks (worst-case overhead)
        sec_header = section["section"].split("\n")[0]
        continuation = f"{sec_header} (pokračování)\n"

        # Budget for the body = max chars minus prefix and continuation overhead
        body_budget = MAX_SECTION_CHARS - len(prefix) - len(continuation)

        if len(body) <= body_budget:
            # Keep whole — this is the common case
            full_text = prefix + body

            if len(full_text) >= MIN_CHUNK_CHARS:
                chunks.append(
                    {
                        "doc_id": f"{law_name}_{chunk_idx:05d}",
                        "page": _section_to_num(section["section"]) or (chunk_idx + 1),
                        "text": full_text,
                        "metadata": {
                            "law": law_name,
                            "section": section["section"],
                            "part": section["part"],
                        },
                    }
                )
                chunk_idx += 1
        else:
            # Large section -- split body at paragraph boundaries
            sub_chunks = _split_text_recursive(body, body_budget, OVERLAP_CHARS)
            for i, sub in enumerate(sub_chunks):
                if i > 0:
                    full_text = prefix + continuation + sub
                else:
                    full_text = prefix + sub

                if len(full_text) >= MIN_CHUNK_CHARS:
                    chunks.append(
                        {
                            "doc_id": f"{law_name}_{chunk_idx:05d}",
                            "page": _section_to_num(section["section"]) or (chunk_idx + 1),
                            "text": full_text,
                            "metadata": {
                                "law": law_name,
                                "section": section["section"],
                                "part": section["part"],
                            },
                        }
                    )
                    chunk_idx += 1

    assert all(len(c["text"]) <= MAX_SECTION_CHARS for c in chunks), (
        f"chunk too large: max {max(len(c['text']) for c in chunks)} chars exceeds limit of {MAX_SECTION_CHARS}"
    )
    return chunks


def main() -> None:
    all_chunks: list[dict] = []

    txt_files = sorted(INPUT_DIR.glob("*.txt"))
    if not txt_files:
        logger.error("No .txt files found in %s", INPUT_DIR)
        return

    for txt_file in txt_files:
        law_name = txt_file.stem
        text = txt_file.read_text(encoding="utf-8")
        logger.info("Chunking %s (%d chars)...", law_name, len(text))
        chunks = chunk_law_text(text, law_name)
        logger.info(
            "  → %d chunks (avg %d chars)", len(chunks), sum(len(c["text"]) for c in chunks) // max(len(chunks), 1)
        )
        all_chunks.extend(chunks)

    OUTPUT_FILE.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=2))
    logger.info("Total: %d chunks written to %s", len(all_chunks), OUTPUT_FILE)

    # Verify § 51 of zákoník práce is complete
    for c in all_chunks:
        if c["metadata"]["law"] == "zakonik_prace" and "§ 51" in c["metadata"].get("section", ""):
            logger.info("§ 51 chunk: doc_id=%s, %d chars, text[:200]=%r", c["doc_id"], len(c["text"]), c["text"][:200])
            if "2 měsíce" in c["text"] or "dva měsíce" in c["text"].lower():
                logger.info("  ✓ Contains the 2-month notice period")
            else:
                logger.warning("  ✗ Missing the 2-month notice period!")
            break


if __name__ == "__main__":
    main()
