#!/usr/bin/env python3
"""Chunk Australian legislation text files into section-aware passages.

Strategy:
  - Skip the Table of Contents (TOC) at the start of each file
  - Split on section boundaries (numbered sections like "1 Short title")
  - Track Part/Division/Chapter/Schedule structural context
  - If a section is under MAX_SECTION_CHARS, keep it whole
  - If a section is too large, split at subsection (1)/(a) boundaries

Reads .txt files from data/corpus/au/ and writes:
    data/corpus/au/chunks.json  — list of chunk dicts

Each chunk:
    {
        "doc_id": "<law_short_name>_<5-digit-idx>",
        "page": <section_number>,
        "text": "[Privacy Act 1988] Part II > Division 1\nSection 6 — Interpretation\n(1) ...",
        "metadata": { "law": "...", "section": "6", "part": "...", "title": "..." }
    }

Usage:
    python3 scripts/chunk_au_corpus.py
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

INPUT_DIR = Path("data/corpus/au")
MANIFEST_PATH = INPUT_DIR / "manifest.json"
OUTPUT_FILE = INPUT_DIR / "chunks.json"

# Chunking limits — matches project-wide strategy
MAX_SECTION_CHARS = 7500
MIN_CHUNK_CHARS = 100
OVERLAP_CHARS = 200


# ---------------------------------------------------------------------------
# Structural pattern matching for Australian legislation
# ---------------------------------------------------------------------------

# Matches section headers like "1 Short title", "6AA Meaning of responsible person",
# "12A Act does not apply...", "267B Notice to..."
SECTION_RE = re.compile(r"^(\d+[A-Z]{0,3})\s+([A-Z].*)")

# Structural headers — Part, Division, Chapter, Schedule, Subdivision
PART_RE = re.compile(r"^(Part\s+\d+[A-Z]?(?:\.\d+)?)\s*[\u2014\u2013\-—–]\s*(.*)", re.IGNORECASE)
CHAPTER_RE = re.compile(r"^(Chapter\s+\d+[A-Z]?)\s*[\u2014\u2013\-—–]\s*(.*)", re.IGNORECASE)
DIVISION_RE = re.compile(r"^(Division\s+\d+[A-Z]?(?:\.\d+)?)\s*[\u2014\u2013\-—–]\s*(.*)", re.IGNORECASE)
SUBDIVISION_RE = re.compile(r"^(Subdivision\s+[A-Z0-9]+(?:\.\d+)?)\s*[\u2014\u2013\-—–]\s*(.*)", re.IGNORECASE)
SCHEDULE_RE = re.compile(r"^(Schedule\s+\d+[A-Z]?)\s*[\u2014\u2013\-—–]\s*(.*)", re.IGNORECASE)

# TOC detection — lines that are just section numbers and titles without content
TOC_SECTION_RE = re.compile(r"^\d+[A-Z]{0,3}\s+[A-Z].*$")


def _section_to_num(sec: str) -> int:
    """Extract numeric part from section string like '6AA' → 6."""
    m = re.match(r"(\d+)", sec)
    return int(m.group(1)) if m else 0


def _detect_body_start(lines: list[str]) -> int:
    """Find where the actual legislation body begins (after TOC).

    The TOC is a sequence of lines that look like section titles but
    without the following subsection content. The body starts when we
    see "An Act relating to..." or a Part/Chapter header followed by
    actual section content.
    """
    # Look for the "An Act relating to..." preamble line
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("An Act "):
            return i

    # Fallback: find first Part header that's followed by section content
    for i, line in enumerate(lines):
        stripped = line.strip()
        if PART_RE.match(stripped) or CHAPTER_RE.match(stripped):
            # Check if the next few lines contain actual section content (subsections)
            for j in range(i + 1, min(i + 20, len(lines))):
                next_line = lines[j].strip()
                if re.match(r"^\(\d+\)", next_line):  # subsection marker
                    return i
    return 0


def _split_into_sections(text: str, law_name: str) -> list[dict]:
    """Split legislation text into raw sections at section boundaries."""
    lines = text.splitlines()

    # Skip TOC
    body_start = _detect_body_start(lines)
    if body_start > 0:
        logger.info("  Body starts at line %d (skipping TOC)", body_start)
        lines = lines[body_start:]

    sections: list[dict] = []
    current_chapter = ""
    current_part = ""
    current_division = ""
    current_subdivision = ""
    current_schedule = ""
    current_section_num = ""
    current_section_title = ""
    current_lines: list[str] = []

    def flush() -> None:
        if current_lines:
            body = "\n".join(current_lines).strip()
            if body and len(body) >= MIN_CHUNK_CHARS:
                sections.append(
                    {
                        "section_num": current_section_num,
                        "section_title": current_section_title,
                        "chapter": current_chapter,
                        "part": current_part,
                        "division": current_division,
                        "subdivision": current_subdivision,
                        "schedule": current_schedule,
                        "body": body,
                    }
                )

    for line in lines:
        stripped = line.strip()
        if not stripped:
            current_lines.append("")
            continue

        # Track structural hierarchy
        m = CHAPTER_RE.match(stripped)
        if m:
            current_chapter = f"{m.group(1)} — {m.group(2)}".strip()
            current_part = ""
            current_division = ""
            current_subdivision = ""
            continue

        m = SCHEDULE_RE.match(stripped)
        if m:
            flush()
            current_schedule = f"{m.group(1)} — {m.group(2)}".strip()
            current_chapter = ""
            current_part = ""
            current_division = ""
            current_subdivision = ""
            current_section_num = ""
            current_section_title = m.group(2).strip()
            current_lines = [stripped]
            continue

        m = PART_RE.match(stripped)
        if m:
            current_part = f"{m.group(1)} — {m.group(2)}".strip()
            current_division = ""
            current_subdivision = ""
            continue

        m = DIVISION_RE.match(stripped)
        if m:
            current_division = f"{m.group(1)} — {m.group(2)}".strip()
            current_subdivision = ""
            continue

        m = SUBDIVISION_RE.match(stripped)
        if m:
            current_subdivision = f"{m.group(1)} — {m.group(2)}".strip()
            continue

        # Section boundary — new numbered section starts
        m = SECTION_RE.match(stripped)
        if m:
            # Check it's a real section start (not mid-sentence) by verifying
            # the title starts with uppercase and the number is reasonable
            sec_num = m.group(1)
            sec_title = m.group(2).strip()
            if len(sec_title) > 2:  # filter out very short false matches
                flush()
                current_section_num = sec_num
                current_section_title = sec_title
                current_lines = [stripped]
                continue

        # Regular content line
        current_lines.append(stripped)

    flush()
    return sections


def _split_text_recursive(
    text: str,
    max_chars: int = MAX_SECTION_CHARS,
    overlap: int = OVERLAP_CHARS,
    _depth: int = 0,
) -> list[str]:
    """Recursively split text so every piece is <= max_chars.

    Strategy (tried in order):
      1. Subsection boundaries: (1), (2), etc.
      2. Paragraph boundaries: (a), (b), etc.
      3. Sentence boundaries
      4. Newline boundaries
      5. Hard character cut (last resort)
    """
    if len(text) <= max_chars:
        return [text]

    if _depth > 10:
        return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]

    split_patterns = [
        r"(?=\n\(\d+\))",  # subsection marker: (1), (2)
        r"(?=\n\([a-z]+\))",  # paragraph marker: (a), (b)
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
        return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]

    # Greedily accumulate parts into chunks within limit
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


def _build_context_header(section: dict, law_title: str) -> str:
    """Build a context header like [Privacy Act 1988] Part II > Division 1."""
    parts = []
    if section["schedule"]:
        parts.append(section["schedule"])
    if section["chapter"]:
        parts.append(section["chapter"])
    if section["part"]:
        parts.append(section["part"])
    if section["division"]:
        parts.append(section["division"])
    if section["subdivision"]:
        parts.append(section["subdivision"])

    context = " > ".join(parts) if parts else ""
    if context:
        return f"[{law_title}] {context}\n"
    return f"[{law_title}]\n"


def chunk_law_text(text: str, law_name: str, law_title: str) -> list[dict]:
    """Split a law text into section-aware chunks."""
    raw_sections = _split_into_sections(text, law_name)
    logger.info("  Found %d raw sections", len(raw_sections))

    chunks: list[dict] = []
    chunk_idx = 0

    for section in raw_sections:
        header = _build_context_header(section, law_title)
        body = section["body"]

        # Continuation header for split sections
        sec_label = f"Section {section['section_num']}" if section["section_num"] else ""
        continuation = f"{sec_label} (continued)\n" if sec_label else ""

        body_budget = MAX_SECTION_CHARS - len(header) - len(continuation)

        if len(body) <= body_budget:
            full_text = header + body
            if len(full_text) >= MIN_CHUNK_CHARS:
                chunks.append(
                    {
                        "doc_id": f"{law_name}_{chunk_idx:05d}",
                        "page": _section_to_num(section["section_num"]) or (chunk_idx + 1),
                        "text": full_text,
                        "metadata": {
                            "law": law_name,
                            "title": law_title,
                            "section": section["section_num"],
                            "section_title": section["section_title"],
                            "part": section["part"],
                            "chapter": section["chapter"],
                        },
                    }
                )
                chunk_idx += 1
        else:
            sub_chunks = _split_text_recursive(body, body_budget, OVERLAP_CHARS)
            for i, sub in enumerate(sub_chunks):
                if i > 0:
                    full_text = header + continuation + sub
                else:
                    full_text = header + sub
                if len(full_text) >= MIN_CHUNK_CHARS:
                    chunks.append(
                        {
                            "doc_id": f"{law_name}_{chunk_idx:05d}",
                            "page": _section_to_num(section["section_num"]) or (chunk_idx + 1),
                            "text": full_text,
                            "metadata": {
                                "law": law_name,
                                "title": law_title,
                                "section": section["section_num"],
                                "section_title": section["section_title"],
                                "part": section["part"],
                                "chapter": section["chapter"],
                            },
                        }
                    )
                    chunk_idx += 1

    # Verify no chunk exceeds the limit
    oversized = [c for c in chunks if len(c["text"]) > MAX_SECTION_CHARS]
    if oversized:
        logger.warning(
            "  %d chunks exceed %d chars (max: %d)",
            len(oversized),
            MAX_SECTION_CHARS,
            max(len(c["text"]) for c in oversized),
        )

    return chunks


def main() -> None:
    # Load manifest for title lookup
    titles: dict[str, str] = {}
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())
        for entry in manifest:
            titles[entry["short_name"]] = entry["title"]

    all_chunks: list[dict] = []

    txt_files = sorted(INPUT_DIR.glob("*.txt"))
    if not txt_files:
        logger.error("No .txt files found in %s", INPUT_DIR)
        return

    for txt_file in txt_files:
        law_name = txt_file.stem
        law_title = titles.get(law_name, law_name.replace("_", " ").title())
        text = txt_file.read_text(encoding="utf-8")
        logger.info("Chunking %s (%d chars)...", law_name, len(text))
        chunks = chunk_law_text(text, law_name, law_title)
        avg_chars = sum(len(c["text"]) for c in chunks) // max(len(chunks), 1)
        logger.info("  → %d chunks (avg %d chars)", len(chunks), avg_chars)
        all_chunks.extend(chunks)

    OUTPUT_FILE.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=2))
    logger.info("Total: %d chunks written to %s", len(all_chunks), OUTPUT_FILE)

    # Summary stats
    total_chars = sum(len(c["text"]) for c in all_chunks)
    avg = total_chars // max(len(all_chunks), 1)
    max_c = max(len(c["text"]) for c in all_chunks) if all_chunks else 0
    min_c = min(len(c["text"]) for c in all_chunks) if all_chunks else 0
    logger.info("Stats: total=%d chars, avg=%d, min=%d, max=%d", total_chars, avg, min_c, max_c)


if __name__ == "__main__":
    main()
