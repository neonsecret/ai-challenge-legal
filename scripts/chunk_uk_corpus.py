#!/usr/bin/env python3
"""Chunk UK legislation text files into section-aware passages.

Strategy:
  - Split on Section boundaries (UK legislation uses numbered sections)
  - Preserve Part > Chapter > Section hierarchy
  - If a section fits within ~7500 chars, keep it whole
  - If a section is too large, split at subsection (1), (2) boundaries
  - Each chunk includes the section header and structural context

Reads .txt files from data/corpus/uk/ and writes:
    data/corpus/uk/chunks.json  — list of chunk dicts

Each chunk:
    {
        "doc_id": "<law_short_name>_<5-digit-idx>",
        "page": <section_number>,
        "text": "[Companies Act 2006] Part 1 > Chapter 2\nSection 51\n(1) ...",
        "metadata": { "law": "...", "section": "Section 51", "part": "..." }
    }

Usage:
    python3 scripts/chunk_uk_corpus.py
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

INPUT_DIR = Path("data/corpus/uk")
OUTPUT_FILE = Path("data/corpus/uk/chunks.json")

# Chunking parameters matching the project standard
MAX_SECTION_CHARS = 7500
MIN_CHUNK_CHARS = 100
OVERLAP_CHARS = 200

# Friendly names for display
ACT_DISPLAY_NAMES: dict[str, str] = {
    "companies_act_2006": "Companies Act 2006",
    "employment_rights_act_1996": "Employment Rights Act 1996",
    "consumer_rights_act_2015": "Consumer Rights Act 2015",
    "equality_act_2010": "Equality Act 2010",
    "data_protection_act_2018": "Data Protection Act 2018",
    "insolvency_act_1986": "Insolvency Act 1986",
    "partnership_act_1890": "Partnership Act 1890",
    "sale_of_goods_act_1979": "Sale of Goods Act 1979",
    "limitation_act_1980": "Limitation Act 1980",
    "human_rights_act_1998": "Human Rights Act 1998",
    "arbitration_act_1996": "Arbitration Act 1996",
    "financial_services_markets_act_2000": "Financial Services and Markets Act 2000",
    "bribery_act_2010": "Bribery Act 2010",
    "modern_slavery_act_2015": "Modern Slavery Act 2015",
    "competition_act_1998": "Competition Act 1998",
}

# ---------------------------------------------------------------------------
# Section detection patterns for UK legislation
# ---------------------------------------------------------------------------

# Primary section pattern: "Section N" or "N Title text"
_SECTION_RE = re.compile(
    r'^(?:'
    r'(?:Section|SECTION)\s+(\d+[A-Z]?)'  # "Section 123" or "Section 123A"
    r'|'
    r'(\d+[A-Z]?)\s+[A-Z]'  # "123 General duty" (numbered section with title)
    r')',
    re.MULTILINE,
)

# Part/Chapter/Schedule structural markers
_PART_RE = re.compile(r'^(?:Part|PART)\s+(\d+|[IVXLCDM]+)', re.MULTILINE | re.IGNORECASE)
_CHAPTER_RE = re.compile(r'^(?:Chapter|CHAPTER)\s+(\d+|[IVXLCDM]+)', re.MULTILINE | re.IGNORECASE)
_SCHEDULE_RE = re.compile(r'^(?:Schedule|SCHEDULE)\s+(\d+)', re.MULTILINE | re.IGNORECASE)

# Subsection pattern for splitting large sections
_SUBSECTION_RE = re.compile(r'(?=\n\(\d+\))')


def _section_to_num(sec: str) -> int:
    """Extract numeric section number."""
    m = re.search(r"(\d+)", sec)
    return int(m.group(1)) if m else 0


def _split_into_sections(text: str) -> list[dict]:
    """Split UK legislation text into sections with structural context."""
    lines = text.splitlines()
    sections: list[dict] = []

    current_part = ""
    current_chapter = ""
    current_schedule = ""
    current_section = ""
    current_lines: list[str] = []

    # Pattern to detect section starts
    section_start_re = re.compile(
        r'^(?:'
        r'(?:Section|SECTION)\s+\d+[A-Z]?'
        r'|'
        r'\d+[A-Z]?\s+[A-Z][a-z]'  # "123 General duty..."
        r')',
    )

    def flush():
        if current_lines:
            body = "\n".join(current_lines).strip()
            if body and len(body) >= MIN_CHUNK_CHARS:
                sections.append({
                    "section": current_section or "Preamble",
                    "part": current_part,
                    "chapter": current_chapter,
                    "schedule": current_schedule,
                    "body": body,
                })

    for line in lines:
        stripped = line.strip()

        # Skip header lines (metadata added by scraper)
        if stripped.startswith("# "):
            continue

        # Track structural markers
        part_match = _PART_RE.match(stripped)
        if part_match:
            current_part = stripped.split("\n")[0][:120]
            current_chapter = ""

        chapter_match = _CHAPTER_RE.match(stripped)
        if chapter_match:
            current_chapter = stripped.split("\n")[0][:120]

        schedule_match = _SCHEDULE_RE.match(stripped)
        if schedule_match:
            current_schedule = stripped.split("\n")[0][:120]
            current_part = ""
            current_chapter = ""

        # Detect new section start
        if section_start_re.match(stripped):
            flush()
            current_section = stripped.split("\n")[0][:120]
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
    _depth: int = 0,
) -> list[str]:
    """Recursively split text so every piece fits within max_chars.

    Strategy (tried in order):
      1. Subsection boundaries: (1), (2), (3) etc.
      2. Paragraph boundaries (double newline)
      3. Sentence boundaries (. followed by space/newline)
      4. Newline boundaries
      5. Hard character cut (last resort)
    """
    if len(text) <= max_chars:
        return [text]

    # Safety valve
    if _depth > 10:
        return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]

    # Try split strategies in order of preference
    split_patterns = [
        r"(?=\n\(\d+\))",       # subsection marker (1), (2), (3)
        r"\n\n",                 # paragraph boundary
        r"(?<=\.)\s+",          # sentence boundary
        r"\n",                   # any newline
    ]

    parts = None
    for pattern in split_patterns:
        candidate = re.split(pattern, text)
        if len(candidate) > 1:
            parts = candidate
            break

    if parts is None:
        return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]

    # Greedily accumulate parts into chunks
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

    # Recursively split any oversized chunk
    result: list[str] = []
    for chunk in chunks:
        if len(chunk) > max_chars:
            result.extend(_split_text_recursive(chunk, max_chars, overlap, _depth + 1))
        else:
            result.append(chunk)

    return result


def chunk_law_text(text: str, law_name: str) -> list[dict]:
    """Split UK legislation text into section-aware chunks."""
    display_name = ACT_DISPLAY_NAMES.get(law_name, law_name.replace("_", " ").title())
    raw_sections = _split_into_sections(text)
    chunks: list[dict] = []
    chunk_idx = 0

    for section in raw_sections:
        # Build context header
        context_parts = []
        if section["schedule"]:
            context_parts.append(section["schedule"])
        if section["part"]:
            context_parts.append(section["part"])
        if section["chapter"]:
            context_parts.append(section["chapter"])
        context = " > ".join(context_parts) if context_parts else ""

        body = section["body"]

        # Build the prefix
        if context:
            prefix = f"[{display_name}] {context}\n"
        else:
            prefix = f"[{display_name}]\n"

        # Continuation header for split chunks
        sec_header = section["section"].split("\n")[0]
        continuation = f"{sec_header} (continued)\n"

        # Budget for body text
        body_budget = MAX_SECTION_CHARS - len(prefix) - len(continuation)

        if len(body) <= body_budget:
            full_text = prefix + body

            if len(full_text) >= MIN_CHUNK_CHARS:
                chunks.append({
                    "doc_id": f"{law_name}_{chunk_idx:05d}",
                    "page": _section_to_num(section["section"]) or (chunk_idx + 1),
                    "text": full_text,
                    "metadata": {
                        "law": law_name,
                        "display_name": display_name,
                        "section": section["section"],
                        "part": section["part"],
                        "chapter": section["chapter"],
                        "schedule": section["schedule"],
                    },
                })
                chunk_idx += 1
        else:
            # Large section — split at subsection boundaries
            sub_chunks = _split_text_recursive(body, body_budget, OVERLAP_CHARS)
            for i, sub in enumerate(sub_chunks):
                if i > 0:
                    full_text = prefix + continuation + sub
                else:
                    full_text = prefix + sub

                if len(full_text) >= MIN_CHUNK_CHARS:
                    chunks.append({
                        "doc_id": f"{law_name}_{chunk_idx:05d}",
                        "page": _section_to_num(section["section"]) or (chunk_idx + 1),
                        "text": full_text,
                        "metadata": {
                            "law": law_name,
                            "display_name": display_name,
                            "section": section["section"],
                            "part": section["part"],
                            "chapter": section["chapter"],
                            "schedule": section["schedule"],
                        },
                    })
                    chunk_idx += 1

    # Verify no chunk exceeds the limit
    oversized = [c for c in chunks if len(c["text"]) > MAX_SECTION_CHARS]
    if oversized:
        logger.warning(
            "%s: %d chunks exceed %d chars (max: %d). Truncating.",
            law_name, len(oversized), MAX_SECTION_CHARS,
            max(len(c["text"]) for c in oversized),
        )
        for c in oversized:
            c["text"] = c["text"][:MAX_SECTION_CHARS]

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
        avg_chars = sum(len(c["text"]) for c in chunks) // max(len(chunks), 1)
        logger.info("  → %d chunks (avg %d chars)", len(chunks), avg_chars)
        all_chunks.extend(chunks)

    OUTPUT_FILE.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=2))
    logger.info("Total: %d chunks written to %s", len(all_chunks), OUTPUT_FILE)

    # Summary statistics
    total_chars = sum(len(c["text"]) for c in all_chunks)
    avg_chars = total_chars // max(len(all_chunks), 1)
    max_chars = max(len(c["text"]) for c in all_chunks) if all_chunks else 0
    min_chars = min(len(c["text"]) for c in all_chunks) if all_chunks else 0

    print(f"\n{'=' * 60}")
    print("UK CORPUS CHUNKING SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Total chunks:  {len(all_chunks)}")
    print(f"  Total chars:   {total_chars:,}")
    print(f"  Avg chunk:     {avg_chars} chars")
    print(f"  Min chunk:     {min_chars} chars")
    print(f"  Max chunk:     {max_chars} chars")

    # Per-law breakdown
    laws = {}
    for c in all_chunks:
        law = c["metadata"]["law"]
        laws[law] = laws.get(law, 0) + 1

    print(f"\n  {'Law':<50s} {'Chunks':>8}")
    print(f"  {'-' * 50} {'-' * 8}")
    for law_name, count in sorted(laws.items()):
        display = ACT_DISPLAY_NAMES.get(law_name, law_name)
        print(f"  {display:<50s} {count:>8}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
