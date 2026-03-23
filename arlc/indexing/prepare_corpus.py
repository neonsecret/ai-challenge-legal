"""Prepare a new document corpus for the finals pipeline.

End-to-end script that handles:
1. Download documents and questions from platform API
2. Index documents into ChromaDB
3. Extract case metadata (for routing)
4. Build article-to-page index (for law routing)
5. Build law name index (for law routing)
6. Validate all indexes
7. Smoke test (10 questions through the pipeline)

Idempotent: skips steps that are already done.

Usage:
    uv run python prepare_corpus.py                     # Full preparation
    uv run python prepare_corpus.py --skip-download     # Skip download
    uv run python prepare_corpus.py --skip-indexing      # Skip ChromaDB indexing
    uv run python prepare_corpus.py --smoke-test-only    # Just run smoke test
    uv run python prepare_corpus.py --force              # Rebuild everything
"""

import argparse
import asyncio
import json
import os
import random
import shutil
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DOCS_DIR = Path("data/documents")
QUESTIONS_PATH = Path("data/questions.json")
CHROMA_DIR = Path("data/chroma_db")

INDEX_FILES = {
    "case_metadata": Path("data/case_metadata_index.json"),
    "article_page": Path("data/article_page_index.json"),
    "law_name": Path("data/law_name_index.json"),
    "latest_edition": Path("data/latest_edition_index.json"),
}


def _step_header(step_num: int, title: str, skip: bool = False):
    """Print a step header."""
    status = "SKIPPING" if skip else ""
    print(f"\n{'='*60}")
    print(f"  Step {step_num}: {title} {status}")
    print(f"{'='*60}")


# ---------------------------------------------------------------------------
# Step 1: Download documents and questions
# ---------------------------------------------------------------------------

def step_download(force: bool = False):
    """Download documents and questions from platform API."""
    _step_header(1, "Download corpus from platform")

    if not os.environ.get("EVAL_API_KEY"):
        print("  ERROR: EVAL_API_KEY not set. Cannot download from platform.")
        print("  Set it with: export EVAL_API_KEY=your-key")
        print("  Or use --skip-download if you already have the files.")
        sys.exit(1)

    sys.path.insert(0, str(Path(__file__).parent / "starter_kit"))
    from arlc import EvaluationClient

    client = EvaluationClient.from_env()

    # Download questions
    if QUESTIONS_PATH.exists() and not force:
        with open(QUESTIONS_PATH) as f:
            qs = json.load(f)
        print(f"  Questions already exist: {QUESTIONS_PATH} ({len(qs)} questions)")
    else:
        print("  Downloading questions...")
        t0 = time.monotonic()
        questions = client.download_questions(QUESTIONS_PATH)
        elapsed = time.monotonic() - t0
        print(f"  Downloaded {len(questions)} questions in {elapsed:.1f}s")

    # Download documents
    pdfs = list(DOCS_DIR.glob("*.pdf")) if DOCS_DIR.exists() else []
    if pdfs and not force:
        print(f"  Documents already exist: {DOCS_DIR} ({len(pdfs)} PDFs)")
    else:
        print("  Downloading documents...")
        t0 = time.monotonic()
        # Download to temp dir, then move PDFs to data/documents
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        target = client.download_documents(str(DOCS_DIR))
        elapsed = time.monotonic() - t0
        # Count PDFs after extraction
        pdfs = list(DOCS_DIR.glob("*.pdf"))
        # Also check subdirectories (some ZIPs extract into subdirs)
        for subdir in DOCS_DIR.iterdir():
            if subdir.is_dir():
                for pdf in subdir.glob("*.pdf"):
                    dest = DOCS_DIR / pdf.name
                    if not dest.exists():
                        shutil.move(str(pdf), str(dest))
                        pdfs.append(dest)
        pdfs = list(DOCS_DIR.glob("*.pdf"))
        print(f"  Downloaded and extracted {len(pdfs)} PDFs in {elapsed:.1f}s")

    # Clean up zip if present
    zip_path = DOCS_DIR / "documents.zip"
    if zip_path.exists():
        zip_path.unlink()

    return len(pdfs)


# ---------------------------------------------------------------------------
# Step 1.5: Convert PDFs to structured Markdown (Docling)
# ---------------------------------------------------------------------------

def step_docling_convert(force: bool = False):
    """Convert PDFs to structured Markdown using Docling."""
    _step_header("1.5", "Docling PDF → Markdown conversion")

    from docling_converter import OUTPUT_DIR, convert_all

    if OUTPUT_DIR.exists() and not force:
        existing = list(OUTPUT_DIR.glob("*.md"))
        if existing:
            print(f"  Docling output exists: {OUTPUT_DIR} ({len(existing)} docs)")
            print("  Use --force to reconvert")
            return

    print("  Converting PDFs to structured Markdown...")
    t0 = time.monotonic()
    converted = convert_all(force=force)
    elapsed = time.monotonic() - t0
    print(f"  Docling conversion complete in {elapsed:.1f}s ({converted} docs)")


# ---------------------------------------------------------------------------
# Step 2: Index documents into ChromaDB
# ---------------------------------------------------------------------------

def step_index(force: bool = False):
    """Build ChromaDB vector index."""
    _step_header(2, "Index documents into ChromaDB")

    if CHROMA_DIR.exists() and not force:
        print(f"  ChromaDB index exists: {CHROMA_DIR}")
        print("  Use --force to rebuild")
        return

    if force and CHROMA_DIR.exists():
        print("  Removing existing index...")
        shutil.rmtree(CHROMA_DIR)

    from arlc.indexing.indexer import build_index
    print("  Building ChromaDB index...")
    t0 = time.monotonic()
    build_index()
    elapsed = time.monotonic() - t0
    print(f"  Indexing complete in {elapsed:.1f}s")


# ---------------------------------------------------------------------------
# Step 3: Build case metadata index
# ---------------------------------------------------------------------------

def step_case_metadata(force: bool = False):
    """Extract case metadata using build_case_metadata_auto.py."""
    _step_header(3, "Extract case metadata")

    output_path = INDEX_FILES["case_metadata"]

    if output_path.exists() and not force:
        with open(output_path) as f:
            data = json.load(f)
        print(f"  Case metadata exists: {output_path} ({len(data)} entries)")
        return

    # Check for the auto builder
    auto_builder = Path("build_case_metadata_auto.py")
    if not auto_builder.exists():
        # Fall back to original build_case_index.py
        auto_builder = Path("build_case_index.py")

    if not auto_builder.exists():
        print("  ERROR: No metadata builder found (build_case_metadata_auto.py or build_case_index.py)")
        return

    print(f"  Running {auto_builder.name}...")
    t0 = time.monotonic()
    os.system(f"uv run python {auto_builder} --docs-dir {DOCS_DIR}")
    elapsed = time.monotonic() - t0

    # The auto builder outputs to a different path
    auto_output = Path("data/case_metadata_index_auto.json")
    if auto_output.exists() and not output_path.exists():
        shutil.copy2(auto_output, output_path)
        print(f"  Copied auto output to {output_path}")

    if output_path.exists():
        with open(output_path) as f:
            data = json.load(f)
        print(f"  Case metadata built in {elapsed:.1f}s ({len(data)} entries)")
    else:
        print(f"  WARNING: Case metadata not produced after {elapsed:.1f}s")


# ---------------------------------------------------------------------------
# Step 4: Build article page index
# ---------------------------------------------------------------------------

def step_article_index(force: bool = False):
    """Build article-to-page index for law documents."""
    _step_header(4, "Build article page index")

    output_path = INDEX_FILES["article_page"]

    if output_path.exists() and not force:
        with open(output_path) as f:
            data = json.load(f)
        print(f"  Article index exists: {output_path} ({len(data)} docs)")
        return

    print("  Running build_article_index.py...")
    t0 = time.monotonic()
    os.system("uv run python build_article_index.py")
    elapsed = time.monotonic() - t0

    if output_path.exists():
        with open(output_path) as f:
            data = json.load(f)
        print(f"  Article index built in {elapsed:.1f}s ({len(data)} docs)")
    else:
        print(f"  WARNING: Article index not produced after {elapsed:.1f}s")


# ---------------------------------------------------------------------------
# Step 5: Build law name index
# ---------------------------------------------------------------------------

def step_law_index(force: bool = False):
    """Build law name and latest edition indexes."""
    _step_header(5, "Build law name index")

    output_path = INDEX_FILES["latest_edition"]

    if output_path.exists() and not force:
        with open(output_path) as f:
            data = json.load(f)
        print(f"  Law index exists: {output_path} ({len(data)} editions)")
        return

    print("  Running build_law_index_v2.py...")
    t0 = time.monotonic()
    os.system("uv run python build_law_index_v2.py")
    elapsed = time.monotonic() - t0

    if output_path.exists():
        with open(output_path) as f:
            data = json.load(f)
        print(f"  Law index built in {elapsed:.1f}s ({len(data)} editions)")
    else:
        print(f"  WARNING: Law index not produced after {elapsed:.1f}s")


# ---------------------------------------------------------------------------
# Step 6: Validate all indexes
# ---------------------------------------------------------------------------

def step_validate():
    """Validate that all required indexes exist and are populated."""
    _step_header(6, "Validate indexes")

    all_ok = True
    for name, path in INDEX_FILES.items():
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            count = len(data)
            print(f"  {name:20s}: OK ({count} entries)")
        else:
            print(f"  {name:20s}: MISSING")
            all_ok = False

    # Check documents
    pdfs = list(DOCS_DIR.glob("*.pdf")) if DOCS_DIR.exists() else []
    print(f"  {'documents':20s}: {len(pdfs)} PDFs")

    # Check questions
    if QUESTIONS_PATH.exists():
        with open(QUESTIONS_PATH) as f:
            qs = json.load(f)
        print(f"  {'questions':20s}: {len(qs)} questions")
    else:
        print(f"  {'questions':20s}: MISSING")
        all_ok = False

    # Check ChromaDB
    if CHROMA_DIR.exists():
        print(f"  {'chroma_db':20s}: OK")
    else:
        print(f"  {'chroma_db':20s}: MISSING")
        all_ok = False

    if all_ok:
        print("\n  All indexes validated successfully.")
    else:
        print("\n  WARNING: Some indexes are missing. Pipeline may fail.")

    return all_ok


# ---------------------------------------------------------------------------
# Step 7: Smoke test
# ---------------------------------------------------------------------------

async def step_smoke_test(n_questions: int = 10):
    """Run a smoke test through the pipeline."""
    _step_header(7, f"Smoke test ({n_questions} questions)")

    if not QUESTIONS_PATH.exists():
        print("  ERROR: Questions file not found")
        return False

    with open(QUESTIONS_PATH) as f:
        all_questions = json.load(f)

    # Pick random sample
    sample = random.sample(all_questions, min(n_questions, len(all_questions)))
    print(f"  Testing {len(sample)} random questions...")

    try:
        from arlc.router import route
        from arlc.retriever import retrieve_pages
    except ImportError as e:
        print(f"  ERROR: Cannot import pipeline modules: {e}")
        return False

    successes = 0
    failures = 0
    ppq_values = []

    for i, q in enumerate(sample):
        try:
            # Route
            route_result = route(q["question"], q["answer_type"])
            target_docs = route_result.target_doc_ids

            # Retrieve
            pages = retrieve_pages(q["question"], target_docs, 1, 3, q["answer_type"])
            total_pages = len(pages)
            ppq_values.append(total_pages)

            successes += 1
            print(f"  [{i+1}/{len(sample)}] {q['answer_type']:10s} pages={total_pages} OK")

        except Exception as e:
            failures += 1
            print(f"  [{i+1}/{len(sample)}] {q['answer_type']:10s} FAILED: {e}")

    avg_ppq = sum(ppq_values) / len(ppq_values) if ppq_values else 0
    print(f"\n  Results: {successes} OK, {failures} failed")
    print(f"  PPQ average: {avg_ppq:.2f} (target < 1.3)")

    return failures == 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="Prepare corpus for finals pipeline")
    parser.add_argument("--skip-download", action="store_true", help="Skip downloading from platform")
    parser.add_argument("--skip-indexing", action="store_true", help="Skip ChromaDB indexing")
    parser.add_argument("--smoke-test-only", action="store_true", help="Just run smoke test")
    parser.add_argument("--force", action="store_true", help="Rebuild everything from scratch")
    parser.add_argument("--smoke-count", type=int, default=10, help="Number of smoke test questions")
    args = parser.parse_args()

    t_total_start = time.monotonic()

    print("=" * 60)
    print("  CORPUS PREPARATION")
    print("=" * 60)

    if args.smoke_test_only:
        await step_smoke_test(args.smoke_count)
        return

    # Step 1: Download
    if not args.skip_download:
        n_docs = step_download(force=args.force)
    else:
        _step_header(1, "Download corpus", skip=True)
        pdfs = list(DOCS_DIR.glob("*.pdf")) if DOCS_DIR.exists() else []
        n_docs = len(pdfs)
        print(f"  {n_docs} PDFs in {DOCS_DIR}")

    # Step 1.5: Docling conversion
    step_docling_convert(force=args.force)

    # Step 2: Index
    if not args.skip_indexing:
        step_index(force=args.force)
    else:
        _step_header(2, "ChromaDB indexing", skip=True)

    # Step 3: Case metadata
    step_case_metadata(force=args.force)

    # Step 4: Article index
    step_article_index(force=args.force)

    # Step 5: Law index
    step_law_index(force=args.force)

    # Step 6: Validate
    all_ok = step_validate()

    # Step 7: Smoke test
    if all_ok:
        await step_smoke_test(args.smoke_count)

    # Summary
    t_total = time.monotonic() - t_total_start
    print(f"\n{'='*60}")
    print(f"  PREPARATION COMPLETE ({t_total:.0f}s)")
    print(f"  Documents: {n_docs} PDFs")
    print(f"  Next: uv run python finals.py --questions {QUESTIONS_PATH}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
