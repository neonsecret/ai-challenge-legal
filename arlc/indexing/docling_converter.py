"""Convert PDFs to structured Markdown using Docling.

# Docling approach inspired by IAS Partners (guy4) and structure-first methodology (guy3)

Converts each PDF in data/documents/ to:
  - data/documents_md/{doc_id}.md  (full structured Markdown)
  - data/documents_md/{doc_id}_structure.json  (hierarchy with page numbers)

Falls back to PyMuPDF raw text extraction if Docling fails on a PDF.

Usage:
    python docling_converter.py                    # convert all PDFs
    python docling_converter.py --doc-id abc123    # convert one PDF
    python docling_converter.py --force            # reconvert all even if already done
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import pymupdf

DOCS_DIR = Path("data/documents")
OUTPUT_DIR = Path("data/documents_md")

# Minimum ratio of Docling text length vs PyMuPDF text length.
# If Docling output is >20% shorter, we supplement with PyMuPDF.
MIN_TEXT_RATIO = 0.80

# Pattern to detect legal structure headings for hierarchy extraction
_HEADING_PATTERNS = [
    # Level 0: Major divisions
    (0, re.compile(r"^(PART|DIVISION)\s+[\dIVXivx]+", re.IGNORECASE | re.MULTILINE)),
    # Level 1: Chapters, Schedules, Appendices
    (1, re.compile(r"^(Chapter|Schedule|Appendix)\s+[\dIVXivx]+", re.IGNORECASE | re.MULTILINE)),
    # Level 1: Articles (top-level)
    (1, re.compile(r"^Article\s+\d+[\.\s]", re.IGNORECASE | re.MULTILINE)),
    # Level 2: Sub-articles like Article 5(1)
    (2, re.compile(r"^Article\s+\d+\(\d+\)", re.IGNORECASE | re.MULTILINE)),
    # Level 1: Sections
    (1, re.compile(r"^Section\s+\d+", re.IGNORECASE | re.MULTILINE)),
    # Level 1: Regulation/Rule
    (1, re.compile(r"^(Regulation|Rule)\s+\d+", re.IGNORECASE | re.MULTILINE)),
]

# Strikethrough markers that Docling may produce
_STRIKETHROUGH_RE = re.compile(r"~~.*?~~", re.DOTALL)


def _detect_doc_type(text: str, filename: str) -> str:
    """Detect document type from text content and filename."""
    text_lower = text[:3000].lower()
    if any(
        kw in text_lower
        for kw in ["court of first instance", "court of appeal", "judgment", "claimant", "defendant", "respondent"]
    ):
        return "case"
    if any(kw in text_lower for kw in ["consultation paper", "policy paper"]):
        return "consultation_paper"
    if "court order" in text_lower or "order of the court" in text_lower:
        return "court_order"
    if any(kw in text_lower for kw in ["regulation no", "regulations of", "regulatory"]):
        return "regulation"
    return "law"


def _extract_title(text: str) -> str:
    """Extract document title from first few lines."""
    lines = [ln.strip() for ln in text[:2000].split("\n") if ln.strip()]
    # Take the first non-empty line that looks like a title (not a page number, not too short)
    for line in lines[:10]:
        if len(line) > 10 and not line.isdigit() and not line.startswith("#"):
            return line[:200]
    return lines[0][:200] if lines else "Untitled"


def _extract_structure(text: str, page_map: dict[int, int] | None = None) -> list[dict]:
    """Extract document hierarchy from Markdown text.

    Args:
        text: The full Markdown text of the document.
        page_map: Optional mapping from character offset to page number.

    Returns:
        List of section dicts with heading, page, and level.
    """
    sections = []
    seen = set()

    for level, pattern in _HEADING_PATTERNS:
        for match in pattern.finditer(text):
            heading = match.group(0).strip()
            if heading in seen:
                continue
            seen.add(heading)

            # Determine page number from character offset
            page = 1
            if page_map:
                offset = match.start()
                # Find the largest page-start offset <= match offset
                for char_offset, pg in sorted(page_map.items()):
                    if char_offset <= offset:
                        page = pg
                    else:
                        break

            sections.append(
                {
                    "heading": heading,
                    "page": page,
                    "level": level,
                }
            )

    # Sort by position in document
    sections.sort(key=lambda s: (s["page"], s["level"]))
    return sections


def _pymupdf_extract(pdf_path: Path) -> tuple[str, dict[int, int]]:
    """Extract text from PDF using PyMuPDF as fallback.

    Returns:
        Tuple of (full_text, page_map) where page_map maps char offsets to page numbers.
    """
    doc = pymupdf.open(str(pdf_path))
    parts = []
    page_map = {}
    offset = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text("text")
        page_map[offset] = page_num + 1  # 1-indexed
        parts.append(page_text)
        offset += len(page_text) + 1  # +1 for the newline we'll join with

    doc.close()
    return "\n".join(parts), page_map


def _remove_strikethrough(text: str) -> str:
    """Remove strikethrough text (legal amendment artifacts)."""
    return _STRIKETHROUGH_RE.sub("", text)


def convert_pdf(pdf_path: Path, force: bool = False) -> tuple[Path, Path] | None:
    """Convert a single PDF to structured Markdown + structure JSON.

    Args:
        pdf_path: Path to the PDF file.
        force: If True, reconvert even if output already exists.

    Returns:
        Tuple of (md_path, json_path) on success, None on skip.
    """
    doc_id = pdf_path.stem
    md_path = OUTPUT_DIR / f"{doc_id}.md"
    json_path = OUTPUT_DIR / f"{doc_id}_structure.json"

    if md_path.exists() and json_path.exists() and not force:
        return None  # Already done

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Get PyMuPDF baseline for comparison and fallback
    pymupdf_text, pymupdf_page_map = _pymupdf_extract(pdf_path)

    # Try Docling conversion
    docling_text = None
    docling_page_map = None
    try:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        docling_text = result.document.export_to_markdown()

        # Remove strikethrough text
        docling_text = _remove_strikethrough(docling_text)

        # Build a simple page map from Docling output
        # Docling inserts page break markers or we can estimate from PyMuPDF page lengths
        docling_page_map = {}
        if hasattr(result.document, "pages") and result.document.pages:
            offset = 0
            for i, page in enumerate(result.document.pages):
                docling_page_map[offset] = i + 1
                # Estimate offset from page content length
                page_content = page.export_to_markdown() if hasattr(page, "export_to_markdown") else ""
                offset += len(page_content) + 1
        else:
            # Fall back to PyMuPDF page map as estimate
            docling_page_map = pymupdf_page_map

        # Check text coverage — if Docling output is >20% shorter, supplement
        if len(docling_text.strip()) < len(pymupdf_text.strip()) * MIN_TEXT_RATIO:
            print(
                f"  WARNING: {doc_id[:16]}... Docling output {len(docling_text)} chars vs PyMuPDF {len(pymupdf_text)} chars — supplementing"
            )
            # Append PyMuPDF sections that are missing
            docling_text = docling_text + "\n\n---\n<!-- PyMuPDF supplement for missing text -->\n" + pymupdf_text
            docling_page_map = pymupdf_page_map

    except Exception as e:
        print(f"  WARNING: Docling failed for {doc_id[:16]}...: {e} — falling back to PyMuPDF")
        docling_text = None

    # Use whichever text we got
    if docling_text:
        final_text = docling_text
        page_map = docling_page_map or pymupdf_page_map
    else:
        final_text = pymupdf_text
        page_map = pymupdf_page_map

    # Extract structure
    sections = _extract_structure(final_text, page_map)
    doc_type = _detect_doc_type(final_text, pdf_path.name)
    title = _extract_title(final_text)

    structure = {
        "doc_id": doc_id,
        "type": doc_type,
        "title": title,
        "sections": sections,
    }

    # Write outputs
    md_path.write_text(final_text, encoding="utf-8")
    json_path.write_text(json.dumps(structure, indent=2, ensure_ascii=False), encoding="utf-8")

    return md_path, json_path


def convert_all(force: bool = False) -> int:
    """Convert all PDFs in the documents directory.

    Args:
        force: If True, reconvert all PDFs even if outputs exist.

    Returns:
        Number of PDFs converted (not skipped).
    """
    if not DOCS_DIR.exists():
        print(f"  ERROR: Documents directory not found: {DOCS_DIR}")
        return 0

    pdfs = sorted(DOCS_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"  ERROR: No PDFs found in {DOCS_DIR}")
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    converted = 0
    skipped = 0
    failed = 0

    for i, pdf_path in enumerate(pdfs):
        try:
            result = convert_pdf(pdf_path, force=force)
            if result is None:
                skipped += 1
            else:
                converted += 1
                if (converted + skipped) % 20 == 0 or i == len(pdfs) - 1:
                    print(f"  Progress: {i + 1}/{len(pdfs)} (converted={converted}, skipped={skipped})")
        except Exception as e:
            failed += 1
            print(f"  ERROR: {pdf_path.stem[:16]}...: {e}")

    print(f"  Done: {converted} converted, {skipped} skipped, {failed} failed out of {len(pdfs)} PDFs")
    return converted


def main():
    parser = argparse.ArgumentParser(description="Convert PDFs to structured Markdown using Docling")
    parser.add_argument("--doc-id", type=str, help="Convert a single PDF by doc_id")
    parser.add_argument("--force", action="store_true", help="Reconvert all even if already done")
    args = parser.parse_args()

    t0 = time.monotonic()

    if args.doc_id:
        pdf_path = DOCS_DIR / f"{args.doc_id}.pdf"
        if not pdf_path.exists():
            print(f"ERROR: PDF not found: {pdf_path}")
            sys.exit(1)
        result = convert_pdf(pdf_path, force=args.force)
        if result:
            print(f"Converted {args.doc_id} -> {result[0].name}, {result[1].name}")
        else:
            print("Already done (use --force to reconvert)")
    else:
        print(f"Converting all PDFs in {DOCS_DIR}...")
        convert_all(force=args.force)

    elapsed = time.monotonic() - t0
    print(f"Completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
