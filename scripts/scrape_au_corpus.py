#!/usr/bin/env python3
"""Download key Australian Commonwealth legislation from legislation.gov.au.

The Federal Register of Legislation serves act text as EPUB-embedded HTML.
This script:
  1. Fetches the /latest/text page for each act
  2. Extracts the EPUB document URLs from the page
  3. Downloads each EPUB HTML volume and extracts plain text
  4. Saves one file per act in data/corpus/au/

Usage:
    python3 scripts/scrape_au_corpus.py
    python3 scripts/scrape_au_corpus.py --dry-run   # List acts without downloading

Output:
    data/corpus/au/<short_name>.txt   — plain text per act
    data/corpus/au/manifest.json      — metadata manifest
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("data/corpus/au")
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

BASE_URL = "https://www.legislation.gov.au"

# (catalog_id, short_name, full_title)
ACTS: list[tuple[str, str, str]] = [
    ("C2004A00818", "corporations_act_2001", "Corporations Act 2001"),
    ("C2004A00109", "competition_consumer_act_2010", "Competition and Consumer Act 2010"),
    ("C2009A00028", "fair_work_act_2009", "Fair Work Act 2009"),
    ("C2004A03712", "privacy_act_1988", "Privacy Act 1988"),
    ("C1966A00033", "bankruptcy_act_1966", "Bankruptcy Act 1966"),
    ("C2004A02944", "insurance_contracts_act_1984", "Insurance Contracts Act 1984"),
    ("C2004A00819", "asic_act_2001", "Australian Securities and Investments Commission Act 2001"),
    ("C2004A04633", "superannuation_supervision_act_1993", "Superannuation Industry (Supervision) Act 1993"),
    ("C2004A05145", "telecommunications_act_1997", "Telecommunications Act 1997"),
    ("C2004A00485", "epbc_act_1999", "Environment Protection and Biodiversity Conservation Act 1999"),
    ("C1958A00062", "migration_act_1958", "Migration Act 1958"),
    ("C2004A05138", "income_tax_assessment_act_1997", "Income Tax Assessment Act 1997"),
    ("C2006A00169", "aml_ctf_act_2006", "Anti-Money Laundering and Counter-Terrorism Financing Act 2006"),
    ("C2011A00137", "whs_act_2011", "Work Health and Safety Act 2011"),
    ("C2009A00134", "consumer_credit_act_2009", "National Consumer Credit Protection Act 2009"),
]

HEADERS = {
    "User-Agent": "VitreonLegal/1.0 (legal-research; contact@vitreon.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
}

RATE_LIMIT_DELAY = 1.5  # seconds between requests
MAX_RETRIES = 3
RETRY_DELAY = 5.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HTML text extraction
# ---------------------------------------------------------------------------

class LegislationTextExtractor(HTMLParser):
    """Extract plain text from legislation.gov.au EPUB HTML pages.

    Strips all HTML tags and extracts meaningful text content,
    preserving paragraph structure.
    """

    SKIP_TAGS = {"script", "style", "nav", "header", "footer", "iframe", "svg", "meta", "link"}
    BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "br",
                  "section", "article", "blockquote", "dt", "dd", "figcaption", "td", "th"}

    def __init__(self) -> None:
        super().__init__()
        self.skip_depth = 0
        self.fragments: list[str] = []
        self._current_line: list[str] = []
        self._tag_stack: list[str] = []

    def _flush_line(self) -> None:
        text = " ".join(self._current_line).strip()
        if text:
            self.fragments.append(text)
        self._current_line = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        self._tag_stack.append(tag)
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if tag in self.BLOCK_TAGS:
            self._flush_line()

    def handle_endtag(self, tag: str) -> None:
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
        if tag in self.SKIP_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1
            return
        if tag in self.BLOCK_TAGS:
            self._flush_line()

    def handle_data(self, data: str) -> None:
        if self.skip_depth > 0:
            return
        text = data.strip()
        if text:
            self._current_line.append(text)

    def get_text(self) -> str:
        self._flush_line()
        return "\n".join(self.fragments)


def extract_text_from_html(html: str) -> str:
    """Extract plain text from HTML content."""
    parser = LegislationTextExtractor()
    parser.feed(html)
    return parser.get_text()


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def fetch_url(session: requests.Session, url: str) -> Optional[str]:
    """Fetch URL with retries and rate limiting."""
    for attempt in range(MAX_RETRIES):
        time.sleep(RATE_LIMIT_DELAY)
        try:
            resp = session.get(url, timeout=60, allow_redirects=True)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 404:
                logger.warning("404 Not Found: %s", url)
                return None
            elif resp.status_code == 429:
                wait = RETRY_DELAY * (attempt + 2)
                logger.warning("429 Rate limited: %s — backing off %.0fs", url, wait)
                time.sleep(wait)
            else:
                logger.warning("HTTP %d for %s (attempt %d)", resp.status_code, url, attempt + 1)
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
        except requests.RequestException as e:
            logger.warning("Network error for %s: %s (attempt %d)", url, e, attempt + 1)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    return None


# ---------------------------------------------------------------------------
# EPUB URL discovery
# ---------------------------------------------------------------------------

def discover_epub_urls(session: requests.Session, catalog_id: str) -> list[str]:
    """Discover EPUB document HTML URLs for a given act.

    The text page at /{catalog_id}/latest/text embeds an EPUB viewer.
    We extract the document URLs from it.
    """
    text_page_url = f"{BASE_URL}/{catalog_id}/latest/text"
    logger.info("  Fetching text page: %s", text_page_url)
    html = fetch_url(session, text_page_url)
    if not html:
        return []

    # Extract the effective date from the page to build EPUB URLs
    # Pattern: /{catalog_id}/{date1}/{date2}/text/original/epub/OEBPS/document_N/document_N.html
    epub_pattern = re.compile(
        rf'{re.escape(catalog_id)}/(\d{{4}}-\d{{2}}-\d{{2}})/(\d{{4}}-\d{{2}}-\d{{2}})/text/original/epub'
    )
    match = epub_pattern.search(html)
    if not match:
        # Try alternative pattern without double date
        epub_pattern2 = re.compile(
            rf'{re.escape(catalog_id)}/(\d{{4}}-\d{{2}}-\d{{2}})/text/original/epub'
        )
        match2 = epub_pattern2.search(html)
        if not match2:
            logger.warning("  Could not find EPUB date path for %s", catalog_id)
            return []
        date_path = f"{match2.group(1)}"
        epub_base = f"{BASE_URL}/{catalog_id}/{date_path}/text/original/epub/OEBPS"
    else:
        date1, date2 = match.group(1), match.group(2)
        epub_base = f"{BASE_URL}/{catalog_id}/{date1}/{date2}/text/original/epub/OEBPS"

    # Find all document_N references in the page
    doc_refs = set(re.findall(r'document_(\d+)/document_\1\.html', html))
    if not doc_refs:
        # Try simpler pattern
        doc_refs = set(re.findall(r'document_(\d+)', html))

    if not doc_refs:
        # Default: try document_1
        doc_refs = {"1"}

    urls = []
    for doc_num in sorted(doc_refs, key=int):
        url = f"{epub_base}/document_{doc_num}/document_{doc_num}.html"
        urls.append(url)

    logger.info("  Found %d EPUB document(s) for %s", len(urls), catalog_id)
    return urls


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def clean_text(raw: str) -> str:
    """Clean extracted text: remove duplicate blank lines, trim whitespace."""
    lines = raw.splitlines()
    cleaned: list[str] = []
    prev_blank = False
    for line in lines:
        stripped = line.strip()
        is_blank = len(stripped) == 0
        if is_blank and prev_blank:
            continue
        cleaned.append(stripped)
        prev_blank = is_blank

    text = "\n".join(cleaned).strip()

    # Remove common boilerplate from legislation.gov.au
    # e.g. "Prepared by the Office of Parliamentary Counsel, Canberra"
    text = re.sub(
        r'Prepared by the Office of Parliamentary Counsel,?\s*Canberra\s*',
        '', text
    )

    return text


# ---------------------------------------------------------------------------
# Download a single act
# ---------------------------------------------------------------------------

def download_act(
    session: requests.Session,
    catalog_id: str,
    short_name: str,
    full_title: str,
) -> Optional[dict]:
    """Download a single act and return metadata dict, or None on failure."""
    out_path = OUTPUT_DIR / f"{short_name}.txt"

    # Resume: skip if already downloaded with reasonable size
    if out_path.exists() and out_path.stat().st_size > 5_000:
        size = out_path.stat().st_size
        logger.info("Already have %s (%d bytes), skipping.", short_name, size)
        return {
            "catalog_id": catalog_id,
            "short_name": short_name,
            "title": full_title,
            "file": str(out_path),
            "size_bytes": size,
            "status": "skipped",
            "scraped_at": "",
        }

    logger.info("Downloading: %s (%s)", full_title, catalog_id)

    # Discover EPUB document URLs
    epub_urls = discover_epub_urls(session, catalog_id)
    if not epub_urls:
        logger.error("  Failed to discover EPUB URLs for %s", short_name)
        return None

    # Download and extract text from each volume
    all_text_parts: list[str] = []
    for url in epub_urls:
        logger.info("  Fetching volume: %s", url.split("/OEBPS/")[-1])
        html = fetch_url(session, url)
        if html:
            text = extract_text_from_html(html)
            if text and len(text) > 100:
                all_text_parts.append(text)
                logger.info("    Extracted %d chars", len(text))
            else:
                logger.warning("    Volume yielded only %d chars", len(text) if text else 0)
        else:
            logger.warning("    Failed to fetch volume")

    if not all_text_parts:
        logger.error("  No text extracted for %s", short_name)
        return None

    # Combine volumes with separator
    combined = "\n\n".join(all_text_parts)
    combined = f"{full_title}\n{'=' * len(full_title)}\n\n{combined}"
    final_text = clean_text(combined)

    # Write output
    out_path.write_text(final_text, encoding="utf-8")
    logger.info("  Saved %s → %s (%d chars)", short_name, out_path, len(final_text))

    return {
        "catalog_id": catalog_id,
        "short_name": short_name,
        "title": full_title,
        "file": str(out_path),
        "size_bytes": len(final_text.encode("utf-8")),
        "volumes": len(all_text_parts),
        "chars": len(final_text),
        "status": "downloaded",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source_url": f"{BASE_URL}/{catalog_id}/latest/text",
    }


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def load_manifest() -> list[dict]:
    """Load existing manifest or return empty list."""
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    return []


def save_manifest(docs: list[dict]) -> None:
    """Persist manifest to disk."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(docs, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Download Australian legislation corpus")
    parser.add_argument("--dry-run", action="store_true", help="List acts without downloading")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        print(f"{'Short Name':<45} {'Catalog ID':<15} {'Title'}")
        print("-" * 100)
        for catalog_id, short_name, title in ACTS:
            print(f"{short_name:<45} {catalog_id:<15} {title}")
        print(f"\nTotal: {len(ACTS)} acts")
        return

    session = requests.Session()
    session.headers.update(HEADERS)

    manifest = load_manifest()
    downloaded_names = {d["short_name"] for d in manifest if d.get("status") == "downloaded"}

    stats = {"downloaded": 0, "skipped": 0, "failed": 0}

    for catalog_id, short_name, title in ACTS:
        result = download_act(session, catalog_id, short_name, title)

        if result is None:
            stats["failed"] += 1
            manifest.append({
                "catalog_id": catalog_id,
                "short_name": short_name,
                "title": title,
                "status": "failed",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            })
        elif result["status"] == "skipped":
            stats["skipped"] += 1
            # Update manifest entry if it exists, otherwise add
            existing = [d for d in manifest if d["short_name"] == short_name]
            if not existing:
                manifest.append(result)
        else:
            stats["downloaded"] += 1
            # Replace any existing entry
            manifest = [d for d in manifest if d["short_name"] != short_name]
            manifest.append(result)

        save_manifest(manifest)

    print(f"\n{'='*60}")
    print(f"Australian Corpus Download Summary")
    print(f"{'='*60}")
    print(f"  Downloaded: {stats['downloaded']}")
    print(f"  Skipped:    {stats['skipped']}")
    print(f"  Failed:     {stats['failed']}")
    print(f"  Total acts: {len(ACTS)}")

    # Show file sizes
    print(f"\nCorpus files:")
    total_size = 0
    for txt_file in sorted(OUTPUT_DIR.glob("*.txt")):
        size = txt_file.stat().st_size
        total_size += size
        print(f"  {txt_file.name:<50} {size:>10,} bytes")
    print(f"  {'TOTAL':<50} {total_size:>10,} bytes")


if __name__ == "__main__":
    main()
