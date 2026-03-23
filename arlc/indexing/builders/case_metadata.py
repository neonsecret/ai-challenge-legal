#!/usr/bin/env python3
"""
build_case_metadata_auto.py — Automated case metadata extractor for finals (300+ docs).

Reads PDFs, classifies document type (CASE/LAW/REGULATION), extracts structured
metadata using Claude Haiku, and outputs data/case_metadata_index.json.

Usage:
    python build_case_metadata_auto.py [--docs-dir data/documents] [--output data/case_metadata_index_auto.json]
    python build_case_metadata_auto.py --validate   # Compare auto vs manual index
    python build_case_metadata_auto.py --dry-run    # Just classify docs, no LLM calls
"""

import argparse
import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path

import anthropic
import fitz
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DOCS_DIR = Path("data/documents")
OUTPUT_PATH = Path("data/case_metadata_index_auto.json")
MANUAL_INDEX_PATH = Path("data/case_metadata_index.json")

# Concurrency limit for Haiku calls
MAX_CONCURRENT = 10

# Case ID regex
CASE_ID_RE = re.compile(
    r"(CFI|SCT|CA|ARB|ENF|DEC|TCD|ACT)\s*(\d+)\s*/\s*(\d{4})",
    re.IGNORECASE,
)

# Law title patterns on cover pages
LAW_TITLE_RE = re.compile(
    r"([\w\s]+?)\s*(?:LAW|REGULATIONS?)\s*\n\s*DIFC\s+LAW\s+NO\.?\s*(\d+)\s+of\s+(\d{4})",
    re.IGNORECASE,
)

# Date patterns for quick classification
DATE_RE = re.compile(r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b", re.IGNORECASE)

CASE_EXTRACT_PROMPT = """You are a legal metadata extractor for DIFC court documents. Extract structured data from the following court document pages.

DOCUMENT PAGES:
{pages}

Extract the following fields as JSON. Use null for any field not clearly stated. Page numbers are 1-indexed.

CRITICAL RULES:
1. "judge": Extract ALL judges/justices from the case header or cover page. Look for titles like "H.E. Justice", "H.E. Chief Justice", "His Honour", "Judge". If a panel of multiple judges, return ALL of them as a list. Preserve name casing exactly as written in the document.

2. "date_of_issue": This is the date the ORDER or JUDGMENT was ISSUED, NOT the hearing date. Look for these specific labels:
   - "Date of Issue:" or "Date of issue:"
   - "Dated:" near the registrar's signature at the END of the document
   - "Date of Order:" or "Date of Judgment:"
   - "Issued on" or "Issued:"
   If multiple dates appear, prefer the one labeled "Date of Issue" or near the registrar signature. Do NOT use "Hearing date" or "Date of hearing". Format as YYYY-MM-DD.

3. "claim_value": This is the CLAIMED monetary amount — the amount the claimant is SUING FOR. Look for it in phrases like "claims the sum of", "claim in the amount of", "seeks payment of", "claims AED/USD...".
   - Do NOT confuse with "costs ordered" (e.g., "costs fixed at AED 50,000" is NOT the claim value)
   - Do NOT confuse with "security for costs"
   - Do NOT multiply monthly salary by 12 — extract the exact figure stated as the claim
   - Include the currency (AED or USD)

4. "claimant" and "defendant": Use the exact names as they appear in the case caption (between "BETWEEN:" and the judge section). Preserve exact casing from the document. For multiple parties, return a list of objects.

5. "outcome": Summarize from "IT IS HEREBY ORDERED", "ORDER", or the court's final ruling section.

Return ONLY valid JSON (no markdown, no explanation):
{{
  "case_id": "TYPE NNN/YYYY e.g. CFI 057/2025",
  "case_type": "CFI|SCT|CA|ARB|ENF|DEC|TCD|ACT",
  "judge": [
    {{"name": "Full name with title exactly as written", "page": 1}}
  ],
  "date_of_issue": {{"value": "YYYY-MM-DD", "page": 1}},
  "claimant": {{"name": "Name as written in document", "page": 1}},
  "defendant": {{"name": "Name as written in document", "page": 1}},
  "claim_value": {{"value": 0.0, "currency": "AED", "page": 1}},
  "outcome": {{"summary": "Brief description of the order/ruling", "page": 1}},
  "court": {{"name": "Court name", "division": "Division if stated", "page": 1}}
}}

If there are MULTIPLE claimants or defendants, return them as a list:
"claimant": [{{"name": "First Claimant", "page": 1}}, {{"name": "Second Claimant", "page": 1}}]
"defendant": [{{"name": "First Defendant", "page": 1}}, {{"name": "Second Defendant", "page": 1}}]"""

LAW_EXTRACT_PROMPT = """You are a legal metadata extractor for DIFC law documents. Extract metadata from these law document pages.

DOCUMENT PAGES:
{pages}

RULES:
- "law_name": The SHORT name of the law (e.g., "Employment Law", "Trust Law", "General Partnership Law"). Do NOT include "DIFC" or the law number in the name.
- "difc_law_number": The number from "DIFC LAW NO. X of YYYY"
- "year": The original enactment year from "DIFC LAW NO. X of YYYY"
- "consolidated_version": Look for "Consolidated Version No. X" on the cover page
- "amendments": List the amending laws mentioned (e.g., "DIFC Law Amendment Law, DIFC Law No. 1 of 2021")

Extract the following as JSON. Use null for missing fields:
{{
  "law_name": "Short law name, e.g. Employment Law",
  "difc_law_number": 2,
  "year": 2019,
  "consolidated_version": "e.g. Consolidated Version No. 5",
  "consolidated_date": "e.g. July 2025",
  "amendments": ["List of amendment laws that modified this law"],
  "enacted_date": "YYYY-MM-DD if stated",
  "total_articles": null
}}

Return ONLY valid JSON (no markdown, no explanation)."""


def classify_document(doc_path: Path) -> str:
    """Classify a PDF as CASE, LAW, or REGULATION based on first page text."""
    try:
        doc = fitz.open(str(doc_path))
        if len(doc) == 0:
            return "UNKNOWN"
        first_page = doc[0].get_text()[:2000]

        # Check for law indicators
        law_indicators = [
            "DIFC LAW NO.",
            "Consolidated Version",
            "DIFC REGULATIONS",
            "SCHEDULE",
            "Part 1",
            "PRELIMINARY",
        ]
        law_score = sum(1 for ind in law_indicators if ind.upper() in first_page.upper())

        # Check for case indicators
        case_indicators = [
            "BETWEEN",
            "Claimant",
            "Defendant",
            "ORDER",
            "JUDGMENT",
            "COURT OF FIRST INSTANCE",
            "COURT OF APPEAL",
            "SMALL CLAIMS TRIBUNAL",
            "H.E. Justice",
            "H.E. Chief Justice",
            "Claim No.",
        ]
        case_score = sum(1 for ind in case_indicators if ind.upper() in first_page.upper())

        if case_score >= 3:
            return "CASE"
        elif law_score >= 2:
            return "LAW"
        elif case_score >= 1:
            return "CASE"
        elif law_score >= 1:
            return "LAW"
        else:
            return "UNKNOWN"
    except Exception as e:
        logger.warning("Failed to classify %s: %s", doc_path.name, e)
        return "UNKNOWN"


def get_doc_pages(
    doc_path: Path, n_first: int = 3, n_last: int = 3, max_chars_per_page: int = 2000
) -> list[tuple[int, str]]:
    """Extract text from first N and last N pages of a PDF."""
    doc = fitz.open(str(doc_path))
    total = len(doc)
    indices = set(range(min(n_first, total)))
    if total > n_first:
        last_start = max(n_first, total - n_last)
        indices.update(range(last_start, total))

    pages = []
    for i in sorted(indices):
        text = doc[i].get_text()[:max_chars_per_page]
        if text.strip():
            pages.append((i + 1, text))

    return pages


def normalize_case_id(raw_id: str) -> str:
    """Normalize a case ID to the canonical format: 'CFI 057/2025' (3-digit zero-padded)."""
    match = CASE_ID_RE.search(raw_id)
    if match:
        prefix = match.group(1).upper()
        number = match.group(2).zfill(3)
        year = match.group(3)
        return f"{prefix} {number}/{year}"
    return raw_id.strip()


def quick_extract_case_id(text: str) -> str | None:
    """Try to extract case ID from text without LLM."""
    match = CASE_ID_RE.search(text)
    if match:
        prefix = match.group(1).upper()
        number = match.group(2).zfill(3)
        year = match.group(3)
        return f"{prefix} {number}/{year}"
    return None


async def extract_case_metadata(
    client: anthropic.AsyncAnthropic,
    doc_id: str,
    doc_path: Path,
    semaphore: asyncio.Semaphore,
) -> dict | None:
    """Extract metadata from a case document using Haiku."""
    pages = get_doc_pages(doc_path)
    if not pages:
        logger.warning("No text extracted from %s", doc_id[:16])
        return None

    pages_text = "\n\n".join(f"[Page {p}]\n{t}" for p, t in pages)

    async with semaphore:
        try:
            resp = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1500,
                messages=[
                    {
                        "role": "user",
                        "content": CASE_EXTRACT_PROMPT.format(pages=pages_text),
                    }
                ],
            )
            text = resp.content[0].text

            # Extract JSON from response
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                data = json.loads(m.group())
                # Normalize judge field to always be a list
                judge = data.get("judge")
                if judge and isinstance(judge, dict):
                    data["judge"] = [judge]
                return data
        except json.JSONDecodeError as e:
            logger.warning("JSON parse error for %s: %s", doc_id[:16], e)
        except Exception as e:
            logger.warning("API error for %s: %s", doc_id[:16], e)

    return None


async def extract_law_metadata(
    client: anthropic.AsyncAnthropic,
    doc_id: str,
    doc_path: Path,
    semaphore: asyncio.Semaphore,
) -> dict | None:
    """Extract metadata from a law document using Haiku."""
    pages = get_doc_pages(doc_path, n_first=2, n_last=0)
    if not pages:
        return None

    pages_text = "\n\n".join(f"[Page {p}]\n{t}" for p, t in pages)

    async with semaphore:
        try:
            resp = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=800,
                messages=[
                    {
                        "role": "user",
                        "content": LAW_EXTRACT_PROMPT.format(pages=pages_text),
                    }
                ],
            )
            text = resp.content[0].text
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception as e:
            logger.warning("API error for law %s: %s", doc_id[:16], e)
    return None


async def process_all_docs(
    docs_dir: Path, max_concurrent: int = MAX_CONCURRENT
) -> tuple[dict, dict]:
    """Process all PDFs and return (case_index, law_index)."""
    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    semaphore = asyncio.Semaphore(max_concurrent)

    pdf_files = sorted(docs_dir.glob("*.pdf"))
    logger.info("Found %d PDFs in %s", len(pdf_files), docs_dir)

    # Phase 1: Classify all documents
    classifications = {}
    for pdf in pdf_files:
        doc_id = pdf.stem
        doc_type = classify_document(pdf)
        classifications[doc_id] = doc_type
        logger.info("  %s... -> %s", doc_id[:16], doc_type)

    case_docs = {k: v for k, v in classifications.items() if v == "CASE"}
    law_docs = {k: v for k, v in classifications.items() if v == "LAW"}
    unknown_docs = {k: v for k, v in classifications.items() if v == "UNKNOWN"}

    logger.info(
        "Classification: %d CASE, %d LAW, %d UNKNOWN",
        len(case_docs),
        len(law_docs),
        len(unknown_docs),
    )

    # Phase 2: Extract case metadata concurrently
    case_tasks = {}
    for doc_id in case_docs:
        doc_path = docs_dir / f"{doc_id}.pdf"
        task = asyncio.create_task(
            extract_case_metadata(client, doc_id, doc_path, semaphore)
        )
        case_tasks[doc_id] = task

    law_tasks = {}
    for doc_id in law_docs:
        doc_path = docs_dir / f"{doc_id}.pdf"
        task = asyncio.create_task(
            extract_law_metadata(client, doc_id, doc_path, semaphore)
        )
        law_tasks[doc_id] = task

    # Gather results
    case_results = {}
    for doc_id, task in case_tasks.items():
        result = await task
        if result:
            case_results[doc_id] = result
            logger.info("  Extracted case: %s -> %s", doc_id[:16], result.get("case_id"))
        else:
            logger.warning("  Failed to extract: %s", doc_id[:16])

    law_results = {}
    for doc_id, task in law_tasks.items():
        result = await task
        if result:
            law_results[doc_id] = result
            logger.info("  Extracted law: %s -> %s", doc_id[:16], result.get("law_name"))

    # Phase 3: Build case index grouped by case_id
    case_index = {}
    for doc_id, meta in case_results.items():
        case_id = meta.get("case_id")
        if not case_id:
            # Try regex fallback
            doc_path = docs_dir / f"{doc_id}.pdf"
            pages = get_doc_pages(doc_path, n_first=1, n_last=0)
            if pages:
                case_id = quick_extract_case_id(pages[0][1])
            if not case_id:
                logger.warning("No case_id for %s, skipping", doc_id[:16])
                continue
            meta["case_id"] = case_id

        case_id = normalize_case_id(case_id)
        if case_id not in case_index:
            case_index[case_id] = {"docs": []}
        case_index[case_id]["docs"].append({"doc_id": doc_id, "metadata": meta})

    return case_index, law_results


def validate_against_manual(auto_index: dict, manual_path: Path = MANUAL_INDEX_PATH):
    """Compare auto-extracted index against manually corrected one."""
    if not manual_path.exists():
        logger.warning("Manual index not found at %s", manual_path)
        return

    with open(manual_path) as f:
        manual_index = json.load(f)

    print(f"\n{'='*80}")
    print("VALIDATION: Auto vs Manual Index")
    print(f"{'='*80}")

    # Compare case IDs
    auto_cases = set(auto_index.keys())
    manual_cases = set(manual_index.keys())

    matched = auto_cases & manual_cases
    auto_only = auto_cases - manual_cases
    manual_only = manual_cases - auto_cases

    print(f"\n  Cases in both:     {len(matched)}")
    print(f"  Auto-only:         {len(auto_only)}  {auto_only if auto_only else ''}")
    print(f"  Manual-only:       {len(manual_only)}  {manual_only if manual_only else ''}")

    # Compare doc counts per case
    print(f"\n  Per-case doc count comparison:")
    for case_id in sorted(matched):
        auto_docs = len(auto_index[case_id]["docs"])
        manual_docs = len(manual_index[case_id]["docs"])
        status = "OK" if auto_docs == manual_docs else "MISMATCH"
        print(f"    {case_id:20s}  auto={auto_docs}  manual={manual_docs}  [{status}]")

    # Compare metadata fields for each matched doc
    print(f"\n  Field-level comparison:")
    total_fields = 0
    correct_fields = 0
    field_stats = {}

    for case_id in sorted(matched):
        auto_docs = {d["doc_id"]: d["metadata"] for d in auto_index[case_id]["docs"]}
        manual_docs = {d["doc_id"]: d["metadata"] for d in manual_index[case_id]["docs"]}

        common_docs = set(auto_docs.keys()) & set(manual_docs.keys())
        for doc_id in common_docs:
            auto_meta = auto_docs[doc_id]
            manual_meta = manual_docs[doc_id]

            for field in ["case_id", "case_type", "date_of_issue"]:
                total_fields += 1
                if field not in field_stats:
                    field_stats[field] = {"total": 0, "correct": 0}
                field_stats[field]["total"] += 1

                auto_val = auto_meta.get(field)
                manual_val = manual_meta.get(field)

                # Normalize for comparison
                if isinstance(auto_val, dict):
                    auto_val = auto_val.get("value")
                if isinstance(manual_val, dict):
                    manual_val = manual_val.get("value")

                if auto_val == manual_val:
                    correct_fields += 1
                    field_stats[field]["correct"] += 1
                else:
                    print(
                        f"    {case_id} [{doc_id[:12]}] {field}: "
                        f"auto={auto_val} vs manual={manual_val}"
                    )

            # Compare parties (also check "defendants" as variant key)
            for party_field in ["claimant", "defendant"]:
                total_fields += 1
                if party_field not in field_stats:
                    field_stats[party_field] = {"total": 0, "correct": 0}
                field_stats[party_field]["total"] += 1

                auto_party = auto_meta.get(party_field, auto_meta.get(party_field + "s", {}))
                manual_party = manual_meta.get(party_field, manual_meta.get(party_field + "s", {}))

                def _extract_names(party) -> set[str]:
                    """Extract set of uppercased names from party field (dict, list, or str)."""
                    if isinstance(party, dict):
                        n = party.get("name", "")
                        return {n.upper().strip()} if n else set()
                    if isinstance(party, list):
                        return {
                            p.get("name", "").upper().strip()
                            for p in party if isinstance(p, dict) and p.get("name")
                        }
                    return {str(party).upper().strip()} if party else set()

                auto_names = _extract_names(auto_party)
                manual_names = _extract_names(manual_party)

                # Match if same set of names (case-insensitive)
                auto_name = ", ".join(sorted(auto_names)) if auto_names else ""
                manual_name = ", ".join(sorted(manual_names)) if manual_names else ""

                if auto_name.upper().strip() == manual_name.upper().strip():
                    correct_fields += 1
                    field_stats[party_field]["correct"] += 1
                else:
                    print(
                        f"    {case_id} [{doc_id[:12]}] {party_field}: "
                        f"auto='{auto_name}' vs manual='{manual_name}'"
                    )

    print(f"\n  Overall accuracy: {correct_fields}/{total_fields} "
          f"({100*correct_fields/total_fields:.1f}%)" if total_fields else "")

    print(f"\n  Per-field accuracy:")
    for field, stats in sorted(field_stats.items()):
        pct = 100 * stats["correct"] / stats["total"] if stats["total"] else 0
        print(f"    {field:20s}  {stats['correct']}/{stats['total']}  ({pct:.0f}%)")

    print(f"{'='*80}\n")


def dry_run(docs_dir: Path):
    """Just classify documents without making API calls."""
    pdf_files = sorted(docs_dir.glob("*.pdf"))
    print(f"\nDry run: classifying {len(pdf_files)} PDFs\n")

    cases = []
    laws = []
    unknown = []

    for pdf in pdf_files:
        doc_id = pdf.stem
        doc_type = classify_document(pdf)

        # Also try regex case ID extraction
        pages = get_doc_pages(pdf, n_first=1, n_last=0)
        case_id = quick_extract_case_id(pages[0][1]) if pages else None

        if doc_type == "CASE":
            cases.append((doc_id, case_id))
            print(f"  CASE  {doc_id[:20]}...  case_id={case_id or 'N/A'}")
        elif doc_type == "LAW":
            laws.append(doc_id)
            print(f"  LAW   {doc_id[:20]}...")
        else:
            unknown.append(doc_id)
            print(f"  ???   {doc_id[:20]}...")

    print(f"\nSummary: {len(cases)} CASE, {len(laws)} LAW, {len(unknown)} UNKNOWN")
    print(f"Case IDs extracted: {sum(1 for _, cid in cases if cid)}/{len(cases)}")


async def main_async(args):
    """Main async entry point."""
    start = time.time()

    case_index, law_index = await process_all_docs(
        Path(args.docs_dir), max_concurrent=args.concurrency
    )

    # Save case index
    output = Path(args.output)
    with open(output, "w") as f:
        json.dump(case_index, f, indent=2, ensure_ascii=False)

    elapsed = time.time() - start
    logger.info(
        "Done in %.1fs: %d cases (%d docs), %d laws. Saved to %s",
        elapsed,
        len(case_index),
        sum(len(c["docs"]) for c in case_index.values()),
        len(law_index),
        output,
    )

    # Save law metadata separately
    if law_index:
        law_output = output.parent / "law_metadata_auto.json"
        with open(law_output, "w") as f:
            json.dump(law_index, f, indent=2, ensure_ascii=False)
        logger.info("Saved %d law metadata entries to %s", len(law_index), law_output)

    if args.validate:
        validate_against_manual(case_index)

    return case_index


def main():
    parser = argparse.ArgumentParser(
        description="Auto-extract case metadata from DIFC legal PDFs"
    )
    parser.add_argument("--docs-dir", default="data/documents", help="PDF directory")
    parser.add_argument(
        "--output",
        default="data/case_metadata_index_auto.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Compare output against manual index",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Just classify docs, no LLM calls",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=MAX_CONCURRENT,
        help="Max concurrent API calls",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.dry_run:
        dry_run(Path(args.docs_dir))
        return

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
