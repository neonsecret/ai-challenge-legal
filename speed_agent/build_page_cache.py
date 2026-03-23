"""Pre-extract all PDF page text to JSON cache for PyPy pipeline.

Run once with CPython: .venv/bin/python speed_agent/build_page_cache.py
Produces speed_agent/page_cache.json: {doc_id: {page_num: text}}
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import pymupdf

DATA_DIR = Path(__file__).parent.parent / "data"
DOCS_DIR = DATA_DIR / "documents"
OUT_PATH = Path(__file__).parent / "page_cache.json"

t0 = time.monotonic()
cache = {}
total_pages = 0

pdfs = sorted(DOCS_DIR.glob("*.pdf"))
print(f"Extracting {len(pdfs)} PDFs...", file=sys.stderr)

for pdf_path in pdfs:
    doc_id = pdf_path.stem
    try:
        doc = pymupdf.open(str(pdf_path))
        pages = {}
        for i, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                pages[str(i + 1)] = text  # JSON keys must be strings
            total_pages += 1
        cache[doc_id] = pages
        doc.close()
    except Exception as e:
        print(f"  ERROR {doc_id[:12]}: {e}", file=sys.stderr)
        cache[doc_id] = {}

with open(OUT_PATH, "w") as f:
    json.dump(cache, f, ensure_ascii=False, separators=(",", ":"))

size_mb = OUT_PATH.stat().st_size / 1024 / 1024
print(f"Done: {total_pages} pages, {len(cache)} docs, {size_mb:.1f}MB → {OUT_PATH}", file=sys.stderr)
print(f"Time: {time.monotonic()-t0:.1f}s", file=sys.stderr)
