#!/usr/bin/env python3
"""Scrape the complete DIFC legal corpus (laws + court judgments) from official sources.

Sources:
  - Laws & Regulations: https://www.difc.ae/business/laws-and-regulations/legal-database/difc-laws/
  - Court Judgments: https://www.difccourts.ae/rules-decisions/judgments-orders/

Usage:
    python3 scripts/scrape_difc_corpus.py                    # Scrape everything
    python3 scripts/scrape_difc_corpus.py --laws-only        # Only laws/regulations
    python3 scripts/scrape_difc_corpus.py --judgments-only   # Only court judgments
    python3 scripts/scrape_difc_corpus.py --dry-run          # Map links without downloading

Output: data/difc_complete/
    laws/           - Law PDFs
    regulations/    - Regulation PDFs
    judgments/      - Court judgment HTML saved as text
    manifest.json   - Full manifest with metadata
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent / "data" / "difc_complete"
LAWS_DIR = BASE_DIR / "laws"
REGULATIONS_DIR = BASE_DIR / "regulations"
JUDGMENTS_DIR = BASE_DIR / "judgments"
MANIFEST_PATH = BASE_DIR / "manifest.json"

DIFC_LAWS_BASE = "https://www.difc.ae"
DIFC_LAWS_DB = f"{DIFC_LAWS_BASE}/business/laws-and-regulations/legal-database/difc-laws/"
DIFC_COURTS_BASE = "https://www.difccourts.ae"

# Known DIFC law page slugs (from tavily map of the legal database)
KNOWN_LAW_SLUGS = [
    "arbitration-law-difc-law-no1-2008",
    "common-reporting-standard-law-difc-law-no-2-2018",
    "companies-law-difc-law-no-5-2018",
    "contract-law-difc-law-no-6-2004",
    "data-protection-law-difc-law-no-5-2020",
    "digital-assets-law-difc-law-no-2-of-2024",
    "electronic-transactions-law-difc-law-no-2-2017",
    "employment-law-difc-law-no-2-of-2019",
    "general-partnership-law-difc-law-no-11-2004",
    "implied-terms-contracts-and-unfair-terms-law-difc-law-no-6-2005",
    "insolvency-law-difc-law-no-1-2019",
    "intellectual-property-law-difc-law-no-4-2019",
    "law-damages-and-remedies-difc-law-no-7-2005",
    "law-obligations-difc-law-no-5-2005",
    "law-relating-application-difc-laws-difc-law-no-10-2005",
    "law-security-difc-law-no-4-2024",
    "leasing-law-difc-law-no-1-2020",
    "limited-liability-partnership-law-difc-law-no-5-2004",
    "limited-partnership-law-difc-law-no-4-2006",
    "netting-law-difc-law-no-2-2014",
    "non-profit-incorporated-organisations-law-difc-law-no-6-2012",
    "operating-law-difc-law-no-7-2018",
    "payment-system-settlement-finality-law-difc-law-no-1-2009",
    "personal-property-law-difc-law-no-9-2005",
    "real-property-law-difc-law-no-10-2018",
    "strata-title-law-difc-law-no-5-2007",
    "trust-law-difc-law-no-4-2018",
    "law-application-civil-and-commercial-laws-difc-difc-law-no-3-2004",
]

# Court divisions with their URL paths and estimated page counts
COURT_DIVISIONS = [
    ("court-first-instance", "Court of First Instance", 299),
    ("court-appeal", "Court of Appeal", 20),
    ("small-claims-tribunal", "Small Claims Tribunal", 64),
    ("arbitration", "Arbitration", 11),
    ("enforcement", "Enforcement", 5),
    ("digital-economy-court", "Digital Economy Court", 2),
    ("court-administrative-orders", "Court Administrative Orders", 3),
]

HEADERS = {
    "User-Agent": "VitreonLegal/1.0 (legal-research; contact@vitreon.app)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

RATE_LIMIT_DELAY = 1.0  # seconds between requests
MAX_CONCURRENT = 3  # max concurrent downloads
MAX_RETRIES = 3
RETRY_DELAY = 5.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DocumentMeta:
    """Metadata for a downloaded document."""
    title: str
    doc_type: str  # "law", "regulation", "judgment"
    court_division: str = ""
    case_number: str = ""
    date: str = ""
    enactment_date: str = ""
    commencement_date: str = ""
    source_url: str = ""
    download_url: str = ""
    local_path: str = ""
    file_size: int = 0
    file_hash: str = ""
    status: str = "active"
    scraped_at: str = ""


@dataclass
class ScrapeStats:
    """Aggregate statistics for the scrape."""
    laws_found: int = 0
    laws_downloaded: int = 0
    laws_skipped: int = 0
    laws_failed: int = 0
    regulations_found: int = 0
    regulations_downloaded: int = 0
    regulations_skipped: int = 0
    regulations_failed: int = 0
    judgments_found: int = 0
    judgments_downloaded: int = 0
    judgments_skipped: int = 0
    judgments_failed: int = 0
    total_size_bytes: int = 0
    total_pages_scraped: int = 0
    errors: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Simple async rate limiter."""

    def __init__(self, delay: float = RATE_LIMIT_DELAY):
        self._delay = delay
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            wait = self._delay - (now - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()


# ---------------------------------------------------------------------------
# Manifest persistence
# ---------------------------------------------------------------------------

def load_manifest() -> list[dict]:
    """Load existing manifest or return empty list."""
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    return []


def save_manifest(docs: list[dict]):
    """Persist manifest to disk."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(docs, f, indent=2, ensure_ascii=False)


def get_downloaded_urls(manifest: list[dict]) -> set[str]:
    """Extract set of already-downloaded source URLs."""
    return {d.get("source_url", "") for d in manifest if d.get("local_path")}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

async def fetch_page(
    client: httpx.AsyncClient,
    url: str,
    limiter: RateLimiter,
    retries: int = MAX_RETRIES,
) -> Optional[str]:
    """Fetch a page with rate limiting and retries. Returns HTML or None."""
    for attempt in range(retries):
        await limiter.acquire()
        try:
            resp = await client.get(url, follow_redirects=True, timeout=30.0)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 403:
                logger.warning("403 Forbidden: %s (attempt %d)", url, attempt + 1)
                if attempt < retries - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
            elif resp.status_code == 429:
                logger.warning("429 Rate limited: %s — backing off", url)
                await asyncio.sleep(RETRY_DELAY * (attempt + 2))
            else:
                logger.warning("HTTP %d for %s", resp.status_code, url)
                if attempt < retries - 1:
                    await asyncio.sleep(RETRY_DELAY)
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            logger.warning("Network error for %s: %s (attempt %d)", url, e, attempt + 1)
            if attempt < retries - 1:
                await asyncio.sleep(RETRY_DELAY)
    return None


async def download_file(
    client: httpx.AsyncClient,
    url: str,
    dest: Path,
    limiter: RateLimiter,
    retries: int = MAX_RETRIES,
) -> Optional[int]:
    """Download a file to dest. Returns file size or None on failure."""
    for attempt in range(retries):
        await limiter.acquire()
        try:
            async with client.stream("GET", url, follow_redirects=True, timeout=60.0) as resp:
                if resp.status_code != 200:
                    logger.warning("HTTP %d downloading %s (attempt %d)", resp.status_code, url, attempt + 1)
                    if attempt < retries - 1:
                        await asyncio.sleep(RETRY_DELAY)
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                size = 0
                with open(dest, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        size += len(chunk)
                return size
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            logger.warning("Download error for %s: %s (attempt %d)", url, e, attempt + 1)
            if dest.exists():
                dest.unlink()
            if attempt < retries - 1:
                await asyncio.sleep(RETRY_DELAY)
    return None


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Create a filesystem-safe slug from text."""
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_]+", "_", text.strip())
    text = re.sub(r"-+", "-", text)
    return text[:200]


def file_hash(path: Path) -> str:
    """Compute SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_text_from_html(html: str) -> str:
    """Extract clean text from a judgment HTML page."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove nav, header, footer, script, style
    for tag in soup.find_all(["nav", "header", "footer", "script", "style", "noscript"]):
        tag.decompose()

    # Try to find the main content area
    main = soup.find("main") or soup.find("article") or soup.find("div", class_="page-content")
    if main:
        text = main.get_text(separator="\n", strip=True)
    else:
        text = soup.get_text(separator="\n", strip=True)

    # Clean up excessive whitespace
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n\n".join(lines)


def extract_judgment_metadata(html: str, url: str) -> dict:
    """Extract case metadata from a judgment page."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()

    meta = {
        "case_number": "",
        "date": "",
        "parties": "",
        "judge": "",
        "court": "",
    }

    # Extract case number from URL
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    case_match = re.match(r"((?:cfi|ca|arb|enf|sct|dec)-?\d+[-/]\d+)", slug, re.I)
    if case_match:
        meta["case_number"] = case_match.group(1).upper().replace("-", " ", 1)

    # Try to find date
    date_match = re.search(r"Date of (?:issue|Judgment|Order)[:\s]*(\d{1,2}\s+\w+\s+\d{4})", text)
    if date_match:
        meta["date"] = date_match.group(1)

    # Try to find judge
    judge_match = re.search(
        r"(?:JUSTICE|Judge|JUDGE)\s+([\w\s.]+?)(?:\n|$|ORDER|JUDGMENT)",
        text, re.I,
    )
    if judge_match:
        meta["judge"] = judge_match.group(1).strip()[:100]

    return meta


# ---------------------------------------------------------------------------
# Laws scraper
# ---------------------------------------------------------------------------

async def scrape_law_page(
    client: httpx.AsyncClient,
    slug: str,
    limiter: RateLimiter,
    downloaded_urls: set[str],
    stats: ScrapeStats,
) -> list[DocumentMeta]:
    """Scrape a single law detail page. Returns list of documents (law + regulations)."""
    page_url = f"{DIFC_LAWS_DB}{slug}"
    docs = []

    html = await fetch_page(client, page_url, limiter)
    if not html:
        logger.error("Failed to fetch law page: %s", page_url)
        stats.laws_failed += 1
        stats.errors.append(f"Failed to fetch: {page_url}")
        return docs

    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text()

    # Extract title
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else slug.replace("-", " ").title()

    # Extract dates
    enactment_date = ""
    commencement_date = ""
    enact_match = re.search(r"Enactment\s*Date[:\s]*(\d{2}\.\d{2}\.\d{4})", page_text)
    if enact_match:
        enactment_date = enact_match.group(1)
    commence_match = re.search(r"Commencement\s*Date[:\s]*(\d{2}\.\d{2}\.\d{4})", page_text)
    if commence_match:
        commencement_date = commence_match.group(1)

    # Extract status (Active/Inactive)
    status = "active"
    if "Inactive" in page_text[:500]:
        status = "inactive"

    # Find PDF download link
    pdf_link = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        link_text = a.get_text(strip=True).lower()
        if "download pdf" in link_text or (href.endswith(".pdf") and "sitecorecloud" in href):
            pdf_link = href
            break

    # Also check for links containing .pdf in the href
    if not pdf_link:
        for a in soup.find_all("a", href=True):
            if a["href"].endswith(".pdf"):
                pdf_link = a["href"]
                break

    if pdf_link:
        if pdf_link in downloaded_urls:
            logger.info("  [SKIP] Already downloaded: %s", title)
            stats.laws_skipped += 1
        else:
            # Download the PDF
            safe_name = slugify(title) + ".pdf"
            dest = LAWS_DIR / safe_name
            size = await download_file(client, pdf_link, dest, limiter)
            if size:
                doc = DocumentMeta(
                    title=title,
                    doc_type="law",
                    enactment_date=enactment_date,
                    commencement_date=commencement_date,
                    source_url=page_url,
                    download_url=pdf_link,
                    local_path=str(dest.relative_to(BASE_DIR)),
                    file_size=size,
                    file_hash=file_hash(dest),
                    status=status,
                    scraped_at=datetime.now(tz=timezone.utc).isoformat(),
                )
                docs.append(doc)
                stats.laws_downloaded += 1
                stats.total_size_bytes += size
                logger.info("  [OK] %s (%d KB)", title, size // 1024)
            else:
                stats.laws_failed += 1
                stats.errors.append(f"Download failed: {pdf_link}")
                logger.error("  [FAIL] Could not download PDF for: %s", title)
    else:
        logger.warning("  [NO PDF] No PDF link found for: %s", title)
        stats.laws_failed += 1

    # Find regulation links on the same page
    reg_section = False
    for a in soup.find_all("a", href=True):
        href = a["href"]
        link_text = a.get_text(strip=True)
        # Check for regulation links (they link to regulation pages on the legal database)
        if "/legal-database/" in href and "regulation" in href.lower():
            reg_url = urljoin(DIFC_LAWS_BASE, href) if href.startswith("/") else href
            if reg_url not in downloaded_urls:
                # We'll scrape regulation pages separately
                reg_doc = DocumentMeta(
                    title=link_text,
                    doc_type="regulation",
                    source_url=reg_url,
                    scraped_at=datetime.now(tz=timezone.utc).isoformat(),
                )
                docs.append(reg_doc)

    stats.laws_found += 1
    return docs


async def scrape_all_laws(
    client: httpx.AsyncClient,
    limiter: RateLimiter,
    downloaded_urls: set[str],
    stats: ScrapeStats,
) -> list[DocumentMeta]:
    """Scrape all known DIFC laws."""
    logger.info("=" * 60)
    logger.info("PHASE 1: Scraping DIFC Laws & Regulations")
    logger.info("=" * 60)

    # First try to discover additional laws from the listing page
    html = await fetch_page(client, DIFC_LAWS_DB, limiter)
    discovered_slugs = set(KNOWN_LAW_SLUGS)

    if html:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/legal-database/difc-laws/" in href:
                slug = href.rstrip("/").split("/")[-1]
                if slug and slug != "difc-laws":
                    discovered_slugs.add(slug)
        logger.info("Discovered %d law slugs (known: %d, new: %d)",
                     len(discovered_slugs), len(KNOWN_LAW_SLUGS),
                     len(discovered_slugs) - len(KNOWN_LAW_SLUGS))
    else:
        logger.warning("Could not fetch laws listing page, using known slugs only")

    all_docs = []
    for i, slug in enumerate(sorted(discovered_slugs), 1):
        logger.info("[%d/%d] Processing law: %s", i, len(discovered_slugs), slug)
        docs = await scrape_law_page(client, slug, limiter, downloaded_urls, stats)
        all_docs.extend(docs)
        # Track downloaded URLs for resume capability
        for doc in docs:
            if doc.download_url:
                downloaded_urls.add(doc.download_url)
            if doc.source_url:
                downloaded_urls.add(doc.source_url)

    logger.info("Laws complete: found=%d, downloaded=%d, skipped=%d, failed=%d",
                stats.laws_found, stats.laws_downloaded, stats.laws_skipped, stats.laws_failed)
    return all_docs


# ---------------------------------------------------------------------------
# Regulations scraper
# ---------------------------------------------------------------------------

async def scrape_regulation_page(
    client: httpx.AsyncClient,
    url: str,
    title: str,
    limiter: RateLimiter,
    downloaded_urls: set[str],
    stats: ScrapeStats,
) -> Optional[DocumentMeta]:
    """Scrape a regulation detail page and download its PDF."""
    if url in downloaded_urls:
        logger.info("  [SKIP] Already downloaded regulation: %s", title)
        stats.regulations_skipped += 1
        return None

    html = await fetch_page(client, url, limiter)
    if not html:
        logger.error("  [FAIL] Could not fetch regulation page: %s", url)
        stats.regulations_failed += 1
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Find PDF link
    pdf_link = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        link_text = a.get_text(strip=True).lower()
        if "download pdf" in link_text or (href.endswith(".pdf") and "sitecorecloud" in href):
            pdf_link = href
            break
    if not pdf_link:
        for a in soup.find_all("a", href=True):
            if a["href"].endswith(".pdf"):
                pdf_link = a["href"]
                break

    if not pdf_link:
        logger.warning("  [NO PDF] No PDF link for regulation: %s", title)
        stats.regulations_failed += 1
        return None

    safe_name = slugify(title) + ".pdf"
    dest = REGULATIONS_DIR / safe_name
    size = await download_file(client, pdf_link, dest, limiter)
    if size:
        doc = DocumentMeta(
            title=title,
            doc_type="regulation",
            source_url=url,
            download_url=pdf_link,
            local_path=str(dest.relative_to(BASE_DIR)),
            file_size=size,
            file_hash=file_hash(dest),
            scraped_at=datetime.now(tz=timezone.utc).isoformat(),
        )
        stats.regulations_downloaded += 1
        stats.regulations_found += 1
        stats.total_size_bytes += size
        logger.info("  [OK] Regulation: %s (%d KB)", title, size // 1024)
        return doc

    stats.regulations_failed += 1
    return None


# ---------------------------------------------------------------------------
# Court judgments scraper
# ---------------------------------------------------------------------------

async def scrape_judgment_listing_page(
    client: httpx.AsyncClient,
    division_slug: str,
    page_num: int,
    limiter: RateLimiter,
) -> list[tuple[str, str, str]]:
    """Scrape a single listing page. Returns list of (title, url, date)."""
    url = (
        f"{DIFC_COURTS_BASE}/rules-decisions/judgments-orders/{division_slug}"
        f"?ccm_paging_p={page_num}&ccm_order_by=ak_date&ccm_order_by_direction=desc"
    )
    html = await fetch_page(client, url, limiter)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    entries = []

    # Judgments are listed as article blocks or h4/h3 headers with links
    # Look for the pattern: link title + date text
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Must be a judgment detail page link
        if f"/rules-decisions/judgments-orders/{division_slug}/" not in href:
            continue
        # Skip pagination links
        if "ccm_paging_p" in href:
            continue

        title = a.get_text(strip=True)
        if not title or len(title) < 5:
            continue

        full_url = urljoin(DIFC_COURTS_BASE, href)

        # Try to find the date near the link
        parent = a.parent
        date_text = ""
        if parent:
            siblings_text = parent.get_text()
            date_match = re.search(
                r"(\w+ \d{1,2}, \d{4})", siblings_text
            )
            if date_match:
                date_text = date_match.group(1)

        entries.append((title, full_url, date_text))

    return entries


async def scrape_judgment_detail(
    client: httpx.AsyncClient,
    title: str,
    url: str,
    date: str,
    division_name: str,
    limiter: RateLimiter,
    downloaded_urls: set[str],
    stats: ScrapeStats,
) -> Optional[DocumentMeta]:
    """Scrape a single judgment page and save as text."""
    if url in downloaded_urls:
        stats.judgments_skipped += 1
        return None

    html = await fetch_page(client, url, limiter)
    if not html:
        stats.judgments_failed += 1
        stats.errors.append(f"Failed judgment: {url}")
        return None

    # Extract clean text
    text = extract_text_from_html(html)
    if len(text) < 100:
        logger.warning("  [EMPTY] Very short content for: %s", title)
        stats.judgments_failed += 1
        return None

    # Extract metadata
    jmeta = extract_judgment_metadata(html, url)

    # Create filename from case number or title
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    safe_name = slugify(slug) + ".txt"

    # Organize by division
    div_slug = division_name.lower().replace(" ", "_")
    dest = JUDGMENTS_DIR / div_slug / safe_name
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Write text with metadata header
    header = f"""# {title}
# Court: {division_name}
# Case Number: {jmeta.get('case_number', '')}
# Date: {date or jmeta.get('date', '')}
# Source: {url}
# ---

"""
    with open(dest, "w", encoding="utf-8") as f:
        f.write(header + text)

    size = dest.stat().st_size

    doc = DocumentMeta(
        title=title,
        doc_type="judgment",
        court_division=division_name,
        case_number=jmeta.get("case_number", ""),
        date=date or jmeta.get("date", ""),
        source_url=url,
        local_path=str(dest.relative_to(BASE_DIR)),
        file_size=size,
        file_hash=file_hash(dest),
        scraped_at=datetime.now(tz=timezone.utc).isoformat(),
    )
    stats.judgments_downloaded += 1
    stats.total_size_bytes += size
    return doc


async def scrape_court_division(
    client: httpx.AsyncClient,
    division_slug: str,
    division_name: str,
    max_pages: int,
    limiter: RateLimiter,
    downloaded_urls: set[str],
    stats: ScrapeStats,
    dry_run: bool = False,
) -> list[DocumentMeta]:
    """Scrape all judgments from a court division."""
    logger.info("--- %s (up to %d pages) ---", division_name, max_pages)

    all_entries = []
    empty_pages = 0

    for page_num in range(1, max_pages + 1):
        entries = await scrape_judgment_listing_page(client, division_slug, page_num, limiter)
        if not entries:
            empty_pages += 1
            if empty_pages >= 2:
                logger.info("  Two consecutive empty pages, stopping at page %d", page_num)
                break
            continue
        empty_pages = 0
        all_entries.extend(entries)
        stats.total_pages_scraped += 1

        if page_num % 10 == 0:
            logger.info("  Listing page %d/%d — %d entries so far", page_num, max_pages, len(all_entries))

    # Deduplicate by URL
    seen_urls = set()
    unique_entries = []
    for title, url, date in all_entries:
        if url not in seen_urls:
            seen_urls.add(url)
            unique_entries.append((title, url, date))

    stats.judgments_found += len(unique_entries)
    logger.info("  Found %d unique judgments in %s", len(unique_entries), division_name)

    if dry_run:
        return []

    # Download judgment details with concurrency control
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    docs = []

    async def fetch_one(title, url, date):
        async with semaphore:
            return await scrape_judgment_detail(
                client, title, url, date, division_name,
                limiter, downloaded_urls, stats,
            )

    # Process in batches to allow periodic saving
    batch_size = 50
    for batch_start in range(0, len(unique_entries), batch_size):
        batch = unique_entries[batch_start:batch_start + batch_size]
        tasks = [fetch_one(t, u, d) for t, u, d in batch]
        results = await asyncio.gather(*tasks)
        for doc in results:
            if doc:
                docs.append(doc)
                downloaded_urls.add(doc.source_url)

        downloaded_in_batch = sum(1 for r in results if r is not None)
        logger.info("  Batch %d-%d: downloaded %d judgments",
                     batch_start + 1, batch_start + len(batch), downloaded_in_batch)

    return docs


async def scrape_all_judgments(
    client: httpx.AsyncClient,
    limiter: RateLimiter,
    downloaded_urls: set[str],
    stats: ScrapeStats,
    dry_run: bool = False,
) -> list[DocumentMeta]:
    """Scrape all court judgments across all divisions."""
    logger.info("=" * 60)
    logger.info("PHASE 2: Scraping DIFC Court Judgments")
    logger.info("=" * 60)

    all_docs = []
    for division_slug, division_name, max_pages in COURT_DIVISIONS:
        docs = await scrape_court_division(
            client, division_slug, division_name, max_pages,
            limiter, downloaded_urls, stats, dry_run,
        )
        all_docs.extend(docs)

        # Save manifest periodically
        if not dry_run and all_docs:
            existing = load_manifest()
            existing_urls = {d["source_url"] for d in existing}
            new_docs = [asdict(d) for d in all_docs if d.source_url not in existing_urls]
            save_manifest(existing + new_docs)

    logger.info("Judgments complete: found=%d, downloaded=%d, skipped=%d, failed=%d",
                stats.judgments_found, stats.judgments_downloaded,
                stats.judgments_skipped, stats.judgments_failed)
    return all_docs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run(args):
    """Main entry point."""
    # Ensure output directories exist
    for d in [LAWS_DIR, REGULATIONS_DIR, JUDGMENTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    # Load existing manifest for resume capability
    existing_manifest = load_manifest()
    downloaded_urls = get_downloaded_urls(existing_manifest)
    logger.info("Loaded manifest with %d existing documents", len(existing_manifest))

    stats = ScrapeStats()
    limiter = RateLimiter(RATE_LIMIT_DELAY)
    all_new_docs: list[DocumentMeta] = []

    async with httpx.AsyncClient(headers=HEADERS) as client:
        # Phase 1: Laws & Regulations
        if not args.judgments_only:
            law_docs = await scrape_all_laws(client, limiter, downloaded_urls, stats)
            all_new_docs.extend(law_docs)

            # Also scrape regulations that were discovered from law pages
            reg_docs_to_scrape = [d for d in law_docs if d.doc_type == "regulation" and not d.local_path]
            if reg_docs_to_scrape:
                logger.info("Scraping %d discovered regulations...", len(reg_docs_to_scrape))
                for i, reg_meta in enumerate(reg_docs_to_scrape, 1):
                    logger.info("[%d/%d] Regulation: %s", i, len(reg_docs_to_scrape), reg_meta.title)
                    result = await scrape_regulation_page(
                        client, reg_meta.source_url, reg_meta.title,
                        limiter, downloaded_urls, stats,
                    )
                    if result:
                        # Replace the placeholder with the real doc
                        all_new_docs = [d for d in all_new_docs if d.source_url != reg_meta.source_url]
                        all_new_docs.append(result)
                        downloaded_urls.add(result.source_url)

        # Phase 2: Court Judgments
        if not args.laws_only:
            judgment_docs = await scrape_all_judgments(
                client, limiter, downloaded_urls, stats, args.dry_run,
            )
            all_new_docs.extend(judgment_docs)

    # Save final manifest (merge with existing)
    if not args.dry_run:
        existing_urls = {d["source_url"] for d in existing_manifest}
        new_doc_dicts = [
            asdict(d) for d in all_new_docs
            if d.source_url not in existing_urls and d.local_path
        ]
        final_manifest = existing_manifest + new_doc_dicts
        save_manifest(final_manifest)
        logger.info("Saved manifest with %d total documents", len(final_manifest))

    # Print summary
    print_summary(stats, all_new_docs, existing_manifest)


def print_summary(stats: ScrapeStats, new_docs: list[DocumentMeta], existing: list[dict]):
    """Print final summary statistics."""
    total_laws = stats.laws_downloaded + stats.laws_skipped
    total_regs = stats.regulations_downloaded + stats.regulations_skipped
    total_judgments = stats.judgments_downloaded + stats.judgments_skipped

    print("\n" + "=" * 60)
    print("DIFC CORPUS SCRAPE SUMMARY")
    print("=" * 60)
    print(f"\n{'Category':<30} {'Found':>8} {'New':>8} {'Skipped':>8} {'Failed':>8}")
    print("-" * 62)
    print(f"{'Laws':<30} {stats.laws_found:>8} {stats.laws_downloaded:>8} {stats.laws_skipped:>8} {stats.laws_failed:>8}")
    print(f"{'Regulations':<30} {stats.regulations_found:>8} {stats.regulations_downloaded:>8} {stats.regulations_skipped:>8} {stats.regulations_failed:>8}")
    print(f"{'Court Judgments':<30} {stats.judgments_found:>8} {stats.judgments_downloaded:>8} {stats.judgments_skipped:>8} {stats.judgments_failed:>8}")
    print("-" * 62)
    total_found = stats.laws_found + stats.regulations_found + stats.judgments_found
    total_new = stats.laws_downloaded + stats.regulations_downloaded + stats.judgments_downloaded
    total_skip = stats.laws_skipped + stats.regulations_skipped + stats.judgments_skipped
    total_fail = stats.laws_failed + stats.regulations_failed + stats.judgments_failed
    print(f"{'TOTAL':<30} {total_found:>8} {total_new:>8} {total_skip:>8} {total_fail:>8}")

    size_mb = stats.total_size_bytes / (1024 * 1024)
    print(f"\nTotal download size: {size_mb:.1f} MB")
    print(f"Listing pages scraped: {stats.total_pages_scraped}")
    print(f"Previously downloaded: {len(existing)}")

    if stats.errors:
        print(f"\nErrors ({len(stats.errors)}):")
        for err in stats.errors[:20]:
            print(f"  - {err}")
        if len(stats.errors) > 20:
            print(f"  ... and {len(stats.errors) - 20} more")

    # Compare with current corpus
    print("\n--- Comparison with current corpus ---")
    print(f"Current corpus: 303 documents, 26,947 chunks")
    print(f"New corpus:     {total_new + len(existing)} documents (new: {total_new})")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Scrape DIFC legal corpus")
    parser.add_argument("--laws-only", action="store_true", help="Only scrape laws/regulations")
    parser.add_argument("--judgments-only", action="store_true", help="Only scrape court judgments")
    parser.add_argument("--dry-run", action="store_true", help="Map links without downloading content")
    args = parser.parse_args()

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
