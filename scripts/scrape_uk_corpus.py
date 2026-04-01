#!/usr/bin/env python3
"""Download key UK legislation from legislation.gov.uk and save as plain text.

legislation.gov.uk provides free access to UK legislation under the
Open Government Licence v3.0 (Crown Copyright).

Strategy:
  - Download each act's full HTML from legislation.gov.uk
  - Parse the HTML to extract clean legislative text
  - Preserve structural elements (Parts, Chapters, Sections, Schedules)
  - Save as one .txt file per act in data/corpus/uk/
  - Create manifest.json with metadata

Usage:
    python3 scripts/scrape_uk_corpus.py
    python3 scripts/scrape_uk_corpus.py --force   # Re-download all
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("data/corpus/uk")
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

BASE_URL = "https://www.legislation.gov.uk"

HEADERS = {
    "User-Agent": "VitreonLegal/1.0 (legal-research; contact@vitreon.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

RATE_LIMIT_DELAY = 2.0  # seconds between requests
MAX_RETRIES = 3
RETRY_DELAY = 5.0
MIN_TEXT_LENGTH = 5000  # minimum chars for a valid act download

# ---------------------------------------------------------------------------
# UK Legislation catalogue
# Each entry: (type, year, chapter, short_name, full_title)
#   type: "ukpga" for UK Public General Acts
# ---------------------------------------------------------------------------

UK_ACTS: list[tuple[str, int, int, str, str]] = [
    ("ukpga", 2006, 46, "companies_act_2006",
     "Companies Act 2006"),
    ("ukpga", 1996, 18, "employment_rights_act_1996",
     "Employment Rights Act 1996"),
    ("ukpga", 2015, 15, "consumer_rights_act_2015",
     "Consumer Rights Act 2015"),
    ("ukpga", 2010, 15, "equality_act_2010",
     "Equality Act 2010"),
    ("ukpga", 2018, 12, "data_protection_act_2018",
     "Data Protection Act 2018"),
    ("ukpga", 1986, 45, "insolvency_act_1986",
     "Insolvency Act 1986"),
    ("ukpga", 1890, 39, "partnership_act_1890",
     "Partnership Act 1890"),
    ("ukpga", 1979, 54, "sale_of_goods_act_1979",
     "Sale of Goods Act 1979"),
    ("ukpga", 1980, 58, "limitation_act_1980",
     "Limitation Act 1980"),
    ("ukpga", 1998, 42, "human_rights_act_1998",
     "Human Rights Act 1998"),
    ("ukpga", 1996, 23, "arbitration_act_1996",
     "Arbitration Act 1996"),
    ("ukpga", 2000, 8, "financial_services_markets_act_2000",
     "Financial Services and Markets Act 2000"),
    ("ukpga", 2010, 23, "bribery_act_2010",
     "Bribery Act 2010"),
    ("ukpga", 2015, 30, "modern_slavery_act_2015",
     "Modern Slavery Act 2015"),
    ("ukpga", 1998, 41, "competition_act_1998",
     "Competition Act 1998"),
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ActMetadata:
    """Metadata for a downloaded act."""
    short_name: str
    full_title: str
    act_type: str
    year: int
    chapter: int
    source_url: str
    local_path: str
    file_size: int = 0
    char_count: int = 0
    section_count: int = 0
    scraped_at: str = ""
    status: str = "ok"
    error: str = ""


# ---------------------------------------------------------------------------
# HTML text extractor
# ---------------------------------------------------------------------------

class LegislationTextExtractor(HTMLParser):
    """Extract clean legislative text from legislation.gov.uk HTML.

    The site serves full act HTML at /ukpga/{year}/{chapter}/data.htm
    with well-structured semantic HTML using classes like:
      - LegSnippet, LegContent — main content wrappers
      - LegPart, LegChapter — structural divisions
      - LegSection, LegP1 — section containers
      - LegText, LegP2Text — text paragraphs
    """

    SKIP_TAGS = frozenset({
        "script", "style", "nav", "header", "footer",
        "iframe", "noscript", "meta", "link",
    })

    # Tags that should emit newlines
    BLOCK_TAGS = frozenset({
        "div", "p", "h1", "h2", "h3", "h4", "h5", "h6",
        "li", "tr", "br", "section", "article", "blockquote",
        "table", "thead", "tbody", "td", "th",
    })

    def __init__(self) -> None:
        super().__init__()
        self.skip_depth = 0
        self.fragments: list[str] = []
        self._tag_stack: list[str] = []
        self._pending_newline = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        tag = tag.lower()
        self._tag_stack.append(tag)

        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return

        if self.skip_depth > 0:
            return

        # Block-level tags start a new line
        if tag in self.BLOCK_TAGS:
            self._pending_newline = True

        # Special handling for br
        if tag == "br":
            self.fragments.append("\n")
            self._pending_newline = False

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()

        if tag in self.SKIP_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1
            return

        if tag in self.BLOCK_TAGS:
            self._pending_newline = True

    def handle_data(self, data: str) -> None:
        if self.skip_depth > 0:
            return

        text = data.strip()
        if not text:
            return

        if self._pending_newline and self.fragments:
            self.fragments.append("\n")
            self._pending_newline = False

        self.fragments.append(text)

    def get_text(self) -> str:
        raw = " ".join(self.fragments)
        # Fix spacing around newlines
        raw = re.sub(r' *\n *', '\n', raw)
        # Collapse multiple blank lines
        raw = re.sub(r'\n{3,}', '\n\n', raw)
        return raw.strip()


def extract_text_from_html(html: str) -> str:
    """Extract clean legislative text from legislation.gov.uk HTML.

    Uses a two-pass approach:
    1. Try BeautifulSoup to find the main content area
    2. Fall back to full-page HTML parsing if content area not found
    """
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # Remove unwanted elements
        for tag in soup.find_all(["script", "style", "nav", "header", "footer",
                                   "noscript", "iframe"]):
            tag.decompose()

        # Try to find the main legislation content
        # legislation.gov.uk uses various wrapper classes
        content = (
            soup.find("div", id="viewLegSnippet")
            or soup.find("div", class_="LegSnippet")
            or soup.find("div", id="content")
            or soup.find("div", class_="LegContent")
            or soup.find("main")
            or soup.find("article")
        )

        if content:
            text = content.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)

    except ImportError:
        # Fallback to stdlib HTMLParser
        parser = LegislationTextExtractor()
        parser.feed(html)
        text = parser.get_text()

    # Clean up the text
    lines = text.splitlines()
    cleaned: list[str] = []
    prev_blank = False

    for line in lines:
        stripped = line.strip()
        is_blank = len(stripped) == 0

        if is_blank and prev_blank:
            continue

        cleaned.append(stripped)
        prev_blank = is_blank

    return "\n".join(cleaned)


# ---------------------------------------------------------------------------
# Download logic
# ---------------------------------------------------------------------------

def _fetch_with_retry(
    session: requests.Session,
    url: str,
    timeout: int = 120,
    max_retries: int = MAX_RETRIES,
) -> Optional[str]:
    """Fetch a URL with retries and exponential backoff.

    Handles HTTP 202 (Accepted) — legislation.gov.uk returns 202 when
    generating large documents asynchronously. We poll with backoff.
    """
    retries_202 = 0
    max_202_retries = 6  # up to ~90s of waiting for async generation

    for attempt in range(max_retries):
        try:
            resp = session.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 202:
                # Server is generating the document asynchronously
                retries_202 += 1
                if retries_202 <= max_202_retries:
                    wait = 10 * retries_202  # 10, 20, 30, 40, 50, 60s
                    logger.info("  HTTP 202 (generating), waiting %ds (poll %d/%d)...",
                               wait, retries_202, max_202_retries)
                    time.sleep(wait)
                    # Don't count 202 as a regular retry
                    attempt = max(0, attempt - 1)
                    continue
                else:
                    logger.warning("  HTTP 202 after %d polls, giving up on %s",
                                  retries_202, url)
                    return None
            elif resp.status_code == 429:
                wait = RETRY_DELAY * (attempt + 2)
                logger.warning("Rate limited (429) for %s, waiting %.0fs", url, wait)
                time.sleep(wait)
            elif resp.status_code in (403, 503):
                wait = RETRY_DELAY * (attempt + 1)
                logger.warning("HTTP %d for %s, retrying in %.0fs", resp.status_code, url, wait)
                time.sleep(wait)
            else:
                logger.error("HTTP %d for %s", resp.status_code, url)
                if attempt < max_retries - 1:
                    time.sleep(RETRY_DELAY)
        except requests.RequestException as e:
            logger.error("Network error for %s: %s (attempt %d/%d)",
                        url, e, attempt + 1, max_retries)
            if attempt < max_retries - 1:
                time.sleep(RETRY_DELAY)

    return None


def _build_act_url(act_type: str, year: int, chapter: int) -> str:
    """Build the URL for downloading the full act text."""
    return f"{BASE_URL}/{act_type}/{year}/{chapter}"


def _count_sections(text: str) -> int:
    """Count the number of sections in the extracted text."""
    # UK legislation uses "Section N" or just numbered sections
    section_pattern = re.compile(
        r'^\s*(?:Section\s+\d+|\d+\s+[A-Z])',
        re.MULTILINE,
    )
    return len(section_pattern.findall(text))


def download_act(
    session: requests.Session,
    act_type: str,
    year: int,
    chapter: int,
    short_name: str,
    full_title: str,
) -> tuple[str | None, ActMetadata]:
    """Download a UK act and return (text, metadata).

    Tries multiple URL patterns:
    1. /data.htm — full act HTML (fastest, single request)
    2. /data.xht — XHTML variant
    3. Plain URL — rendered HTML page
    """
    base_url = _build_act_url(act_type, year, chapter)
    meta = ActMetadata(
        short_name=short_name,
        full_title=full_title,
        act_type=act_type,
        year=year,
        chapter=chapter,
        source_url=base_url,
        local_path=f"{short_name}.txt",
        scraped_at=datetime.now(tz=timezone.utc).isoformat(),
    )

    # Try multiple URL patterns for the full act text
    urls_to_try = [
        (f"{base_url}/data.htm", "data.htm"),
        (f"{base_url}/data.xht", "data.xht"),
        (f"{base_url}", "rendered page"),
    ]

    for url, label in urls_to_try:
        logger.info("  Trying %s (%s)...", label, url)
        html = _fetch_with_retry(session, url, timeout=180)

        if not html:
            logger.warning("  Failed to fetch %s", label)
            continue

        text = extract_text_from_html(html)

        if len(text) >= MIN_TEXT_LENGTH:
            # Add a header with act metadata
            header = (
                f"# {full_title}\n"
                f"# Type: {act_type.upper()}\n"
                f"# Year: {year}, Chapter: {chapter}\n"
                f"# Source: {base_url}\n"
                f"# Downloaded: {meta.scraped_at}\n"
                f"# ---\n\n"
            )
            full_text = header + text

            meta.char_count = len(full_text)
            meta.section_count = _count_sections(text)
            meta.status = "ok"
            logger.info("  OK via %s: %d chars, ~%d sections",
                       label, len(full_text), meta.section_count)
            return full_text, meta

        logger.warning("  %s yielded only %d chars (min: %d), trying next...",
                      label, len(text), MIN_TEXT_LENGTH)

    # All attempts failed
    meta.status = "failed"
    meta.error = "All download methods failed or yielded insufficient text"
    return None, meta


def download_act_by_parts(
    session: requests.Session,
    act_type: str,
    year: int,
    chapter: int,
    short_name: str,
    full_title: str,
) -> tuple[str | None, ActMetadata]:
    """Download a UK act part-by-part for very large acts.

    Fetches the table of contents first, then downloads each part separately.
    Used as fallback for acts too large to download in one request.
    """
    base_url = _build_act_url(act_type, year, chapter)
    meta = ActMetadata(
        short_name=short_name,
        full_title=full_title,
        act_type=act_type,
        year=year,
        chapter=chapter,
        source_url=base_url,
        local_path=f"{short_name}.txt",
        scraped_at=datetime.now(tz=timezone.utc).isoformat(),
    )

    # Get the table of contents to discover parts
    contents_url = f"{base_url}/contents"
    logger.info("  Fetching table of contents: %s", contents_url)
    contents_html = _fetch_with_retry(session, contents_url)

    if not contents_html:
        meta.status = "failed"
        meta.error = "Could not fetch table of contents"
        return None, meta

    # Parse TOC to find part URLs
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(contents_html, "html.parser")
    except ImportError:
        meta.status = "failed"
        meta.error = "BeautifulSoup required for part-by-part download"
        return None, meta

    # Find links to parts — legislation.gov.uk uses /part/N pattern
    part_links: list[tuple[str, str]] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Match part links like /ukpga/2006/46/part/1
        if re.search(rf'/{act_type}/{year}/{chapter}/part/\d+', href):
            part_url = href if href.startswith("http") else BASE_URL + href
            part_title = a.get_text(strip=True)
            if (part_url, part_title) not in part_links:
                part_links.append((part_url, part_title))

    # Also look for schedule links
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(rf'/{act_type}/{year}/{chapter}/schedule/\d+', href):
            sched_url = href if href.startswith("http") else BASE_URL + href
            sched_title = a.get_text(strip=True)
            if (sched_url, sched_title) not in part_links:
                part_links.append((sched_url, sched_title))

    if not part_links:
        logger.warning("  No part links found in TOC, falling back to whole-act download")
        meta.status = "failed"
        meta.error = "No parts found in table of contents"
        return None, meta

    logger.info("  Found %d parts/schedules to download", len(part_links))

    # Download each part
    all_parts: list[str] = []
    for i, (part_url, part_title) in enumerate(part_links, 1):
        logger.info("  [%d/%d] %s", i, len(part_links), part_title or part_url)
        time.sleep(RATE_LIMIT_DELAY)

        part_html = _fetch_with_retry(session, part_url)
        if part_html:
            part_text = extract_text_from_html(part_html)
            if part_text:
                all_parts.append(f"\n\n{'=' * 60}\n{part_title}\n{'=' * 60}\n\n{part_text}")
        else:
            logger.warning("    Failed to download: %s", part_title)

    if not all_parts:
        meta.status = "failed"
        meta.error = "Failed to download any parts"
        return None, meta

    # Assemble full text
    header = (
        f"# {full_title}\n"
        f"# Type: {act_type.upper()}\n"
        f"# Year: {year}, Chapter: {chapter}\n"
        f"# Source: {base_url}\n"
        f"# Parts downloaded: {len(all_parts)}/{len(part_links)}\n"
        f"# Downloaded: {meta.scraped_at}\n"
        f"# ---\n"
    )
    full_text = header + "\n".join(all_parts)

    meta.char_count = len(full_text)
    meta.section_count = _count_sections(full_text)
    meta.status = "ok"
    logger.info("  Assembled %d parts: %d chars, ~%d sections",
               len(all_parts), len(full_text), meta.section_count)
    return full_text, meta


# ---------------------------------------------------------------------------
# Manifest persistence
# ---------------------------------------------------------------------------

def load_manifest() -> list[dict]:
    """Load existing manifest or return empty list."""
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    return []


def save_manifest(manifest: list[dict]) -> None:
    """Save manifest to disk."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Download UK legislation corpus")
    parser.add_argument("--force", action="store_true",
                       help="Re-download all acts even if already present")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing manifest for resume capability
    manifest = load_manifest()
    existing_names = {
        m["short_name"] for m in manifest
        if m.get("status") == "ok" and m.get("char_count", 0) > MIN_TEXT_LENGTH
    }

    session = requests.Session()
    session.headers.update(HEADERS)

    stats = {"downloaded": 0, "skipped": 0, "failed": 0, "by_parts": 0}

    for act_type, year, chapter, short_name, full_title in UK_ACTS:
        out_path = OUTPUT_DIR / f"{short_name}.txt"

        # Resume: skip already-downloaded files
        if not args.force and short_name in existing_names and out_path.exists():
            size = out_path.stat().st_size
            if size > MIN_TEXT_LENGTH:
                logger.info("[SKIP] %s (%d bytes)", short_name, size)
                stats["skipped"] += 1
                continue

        logger.info("[%d/%d] Downloading: %s (%s %d c.%d)",
                   stats["downloaded"] + stats["skipped"] + stats["failed"] + 1,
                   len(UK_ACTS), full_title, act_type, year, chapter)

        # Try full-act download first
        text, meta = download_act(session, act_type, year, chapter,
                                  short_name, full_title)

        # For very large acts or failed downloads, try part-by-part
        if text is None:
            logger.info("  Trying part-by-part download...")
            text, meta = download_act_by_parts(session, act_type, year, chapter,
                                               short_name, full_title)
            if text:
                stats["by_parts"] += 1

        if text:
            out_path.write_text(text, encoding="utf-8")
            meta.file_size = out_path.stat().st_size
            logger.info("[OK] %s → %s (%d chars)",
                       full_title, out_path, meta.char_count)
            stats["downloaded"] += 1
        else:
            logger.error("[FAIL] %s: %s", full_title, meta.error)
            stats["failed"] += 1

        # Update manifest
        manifest = [m for m in manifest if m.get("short_name") != short_name]
        manifest.append(asdict(meta))
        save_manifest(manifest)

        # Rate limiting between acts
        time.sleep(RATE_LIMIT_DELAY)

    # Print summary
    print("\n" + "=" * 60)
    print("UK LEGISLATION CORPUS DOWNLOAD SUMMARY")
    print("=" * 60)
    print(f"  Downloaded:   {stats['downloaded']}")
    print(f"  By parts:     {stats['by_parts']}")
    print(f"  Skipped:      {stats['skipped']}")
    print(f"  Failed:       {stats['failed']}")
    print(f"  Total acts:   {len(UK_ACTS)}")

    # List downloaded files
    txt_files = sorted(OUTPUT_DIR.glob("*.txt"))
    if txt_files:
        total_chars = sum(f.stat().st_size for f in txt_files)
        print(f"\n  Files in {OUTPUT_DIR}/:")
        for f in txt_files:
            print(f"    {f.name:50s} {f.stat().st_size:>10,d} bytes")
        print(f"    {'TOTAL':50s} {total_chars:>10,d} bytes")

    ok_count = sum(1 for m in manifest if m.get("status") == "ok")
    print(f"\n  Manifest: {ok_count}/{len(manifest)} acts OK")
    print("=" * 60)


if __name__ == "__main__":
    main()
