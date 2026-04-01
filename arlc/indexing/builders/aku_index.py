#!/usr/bin/env python3
"""Extract Atomic Knowledge Units (QA-structured facts) from document pages.

# AKU extraction concept from IndexRAG (Bao & Shi, 2026, arXiv:2603.16415)

For each document page, prompts an LLM to extract factual claims as QA pairs.
Output: data/aku_index.json

Usage:
    python build_aku_index.py                         # extract all (uses Haiku)
    python build_aku_index.py --doc-id abc123         # extract one doc
    python build_aku_index.py --model claude-haiku-4-5  # specify model
    python build_aku_index.py --dry-run               # show what would be processed
    python build_aku_index.py --max-docs 5            # process first N docs only
"""

import argparse
import json
import sys
import time
from pathlib import Path

import pymupdf
from dotenv import load_dotenv

load_dotenv()

from arlc.llm import router as llm_router

DOCUMENTS_DIR = Path("data/documents")
DOCUMENTS_MD_DIR = Path("data/documents_md")
AKU_INDEX_PATH = Path("data/aku_index.json")

DEFAULT_MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = """You are a legal document analyst. Extract all factual claims from the given legal document page as question-answer pairs.

Rules:
- Each fact must be self-contained (understandable without the surrounding text)
- Only include facts explicitly stated in the text. Do not infer or hallucinate.
- Questions should be specific and answerable from the text alone
- Answers should be concise but complete
- Include legal references, dates, amounts, names, definitions, obligations, penalties
- Skip boilerplate headers/footers and page numbers

Output a JSON array: [{"q": "...", "a": "..."}]
If the page has no extractable facts (blank, just headers, etc.), output: []"""


def get_pdf_page_texts(doc_id: str) -> list[tuple[int, str]]:
    """Get page texts for a document. Try markdown first, fall back to PyMuPDF.

    Returns list of (page_number, text) tuples (1-based page numbers).
    """
    # Try markdown files first
    md_path = DOCUMENTS_MD_DIR / f"{doc_id}.md"
    if md_path.exists():
        content = md_path.read_text(encoding="utf-8")
        # Split by page markers — docling_converter uses <!-- PAGE N --> markers
        pages = []
        import re

        parts = re.split(r"<!--\s*PAGE\s+(\d+)\s*-->", content)
        if len(parts) > 1:
            # parts: [before_first_marker, page_num, text, page_num, text, ...]
            for i in range(1, len(parts), 2):
                page_num = int(parts[i])
                text = parts[i + 1].strip() if i + 1 < len(parts) else ""
                if text:
                    pages.append((page_num, text))
            if pages:
                return pages
        # If no page markers, treat whole file as page 1
        if content.strip():
            return [(1, content.strip())]

    # Fall back to PyMuPDF
    pdf_path = DOCUMENTS_DIR / f"{doc_id}.pdf"
    if not pdf_path.exists():
        return []

    doc = pymupdf.open(str(pdf_path))
    pages = []
    for page_num in range(len(doc)):
        text = doc[page_num].get_text().strip()
        if text and len(text) > 50:  # skip near-empty pages
            pages.append((page_num + 1, text))
    doc.close()
    return pages


def extract_akus_from_page(doc_id: str, page_num: int, text: str, model: str) -> list[dict]:
    """Extract AKU pairs from a single page using LLM."""
    user_message = f"Document: {doc_id}, Page: {page_num}\n\n{text[:4000]}"

    try:
        response_text, _, _, _, _, _ = llm_router.call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=2048,
            model=model,
        )
    except Exception as e:
        print(f"  [ERROR] LLM call failed for {doc_id} p{page_num}: {e}", file=sys.stderr)
        # Retry once
        try:
            time.sleep(2)
            response_text, _, _, _, _, _ = llm_router.call_llm(
                system_prompt=SYSTEM_PROMPT,
                user_message=user_message,
                max_tokens=2048,
                model=model,
            )
        except Exception as e2:
            print(f"  [SKIP] Retry also failed for {doc_id} p{page_num}: {e2}", file=sys.stderr)
            return []

    # Parse JSON from response
    try:
        # Strip markdown code fences if present
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        pairs = json.loads(cleaned)
        if not isinstance(pairs, list):
            return []

        return [
            {"q": p["q"], "a": p["a"], "page": page_num, "doc_id": doc_id}
            for p in pairs
            if isinstance(p, dict) and "q" in p and "a" in p
        ]
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  [WARN] JSON parse failed for {doc_id} p{page_num}: {e}", file=sys.stderr)
        return []


def load_existing_index() -> tuple[list[dict], set[str]]:
    """Load existing AKU index and return (entries, set of processed doc_ids)."""
    if not AKU_INDEX_PATH.exists():
        return [], set()
    try:
        entries = json.loads(AKU_INDEX_PATH.read_text(encoding="utf-8"))
        doc_ids = {e["doc_id"] for e in entries if "doc_id" in e}
        return entries, doc_ids
    except (json.JSONDecodeError, KeyError):
        return [], set()


def get_all_doc_ids() -> list[str]:
    """Get all document IDs from the documents directory."""
    return sorted(f.stem for f in DOCUMENTS_DIR.glob("*.pdf"))


def main():
    parser = argparse.ArgumentParser(description="Extract AKU (QA facts) from documents")
    parser.add_argument("--doc-id", help="Process a single document ID")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"LLM model (default: {DEFAULT_MODEL})")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed")
    parser.add_argument("--max-docs", type=int, help="Limit number of docs to process")
    parser.add_argument("--force", action="store_true", help="Reprocess even if already in index")
    args = parser.parse_args()

    existing_entries, processed_ids = load_existing_index()

    if args.doc_id:
        doc_ids = [args.doc_id]
    else:
        doc_ids = get_all_doc_ids()

    # Filter already processed (unless --force)
    if not args.force:
        doc_ids = [d for d in doc_ids if d not in processed_ids]

    if args.max_docs:
        doc_ids = doc_ids[: args.max_docs]

    if args.dry_run:
        print(f"Would process {len(doc_ids)} documents with model={args.model}")
        for d in doc_ids[:20]:
            print(f"  {d}")
        if len(doc_ids) > 20:
            print(f"  ... and {len(doc_ids) - 20} more")
        return

    print(f"Processing {len(doc_ids)} documents with model={args.model}", file=sys.stderr)
    if not args.force:
        print(f"Skipping {len(processed_ids)} already processed docs", file=sys.stderr)

    all_new_entries = []
    total_pages = 0

    for i, doc_id in enumerate(doc_ids):
        pages = get_pdf_page_texts(doc_id)
        if not pages:
            print(f"[{i + 1}/{len(doc_ids)}] {doc_id}: no pages found, skipping", file=sys.stderr)
            continue

        print(f"[{i + 1}/{len(doc_ids)}] {doc_id}: {len(pages)} pages", file=sys.stderr, end="", flush=True)

        doc_entries = []
        for page_num, text in pages:
            akus = extract_akus_from_page(doc_id, page_num, text, args.model)
            doc_entries.extend(akus)
            total_pages += 1

        print(f" -> {len(doc_entries)} AKUs", file=sys.stderr)
        all_new_entries.extend(doc_entries)

        # Save incrementally every 10 docs
        if (i + 1) % 10 == 0:
            combined = existing_entries + all_new_entries
            AKU_INDEX_PATH.write_text(
                json.dumps(combined, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"  [SAVED] {len(combined)} total AKUs so far", file=sys.stderr)

    # Final save
    combined = existing_entries + all_new_entries
    AKU_INDEX_PATH.write_text(
        json.dumps(combined, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"\nDone. {len(all_new_entries)} new AKUs from {total_pages} pages across {len(doc_ids)} docs.",
        file=sys.stderr,
    )
    print(f"Total AKUs in index: {len(combined)}", file=sys.stderr)
    print(f"Index saved to: {AKU_INDEX_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
