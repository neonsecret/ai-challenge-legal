"""Czech Supreme Court (Nejvyssi soud) decision scraper.

Downloads decisions from rozhodnuti.nsoud.cz and stores them in the
court_decisions PostgreSQL table.

Usage:
    uv run python scripts/scrape_supreme_court.py --mode bulk --from-year 2010 --to-year 2026
    uv run python scripts/scrape_supreme_court.py --mode sync --days 7
    uv run python scripts/scrape_supreme_court.py --mode fetch-text --ecli ECLI:CZ:NS:2024:...

Architecture:
    - Bulk mode: paginate search results year by year (list-page-only pass for speed),
      then fetch individual metadata pages for ECLI, date, decision_type, statutes.
    - Sync mode: search for decisions from last N days (small batch, always fetches
      individual pages so ECLI is correct).
    - Fetch-text mode: fetch full Anotace text for a specific ECLI and cache in DB.

Rate limiting: 200ms between requests (configurable via _REQUEST_DELAY_S).
Retry: exponential backoff, 3 attempts.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

# Allow running as a script from the repo root
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE = "https://rozhodnuti.nsoud.cz"
_SEARCH_URL = f"{_BASE}/judikatura/judikatura_ns.nsf/searchRozhodnuti2?createdocument"
_DECISION_URL = f"{_BASE}/Judikatura/judikatura_ns.nsf/WebSearch/{{unid}}?openDocument"
_PAGE_SIZE = 60
_REQUEST_DELAY_S = 0.2  # 200ms between requests
_MAX_RETRIES = 3
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; vitreon-legal-bot/1.0; +https://vitreon.app)",
    "Accept": "text/html,application/xhtml+xml;q=0.9",
    "Accept-Language": "cs,en;q=0.8",
}

# Czech law abbreviation → (law_number, law_year) mapping.
# Extended when we encounter new abbreviations.
_LAW_ABBREV: dict[str, tuple[int, int]] = {
    # Criminal Code
    "tr. zákoníku": (40, 2009),
    "tr. z.": (40, 2009),
    "trestního zákoníku": (40, 2009),
    # Civil Code
    "obč. zákoníku": (89, 2012),
    "o. z.": (89, 2012),
    "občanského zákoníku": (89, 2012),
    "občanský zákoník": (89, 2012),
    # Labour Code
    "zákoníku práce": (262, 2006),
    "z. p.": (262, 2006),
    "zák. práce": (262, 2006),
    "zákoník práce": (262, 2006),
    # Business Corporations
    "z. o. k.": (90, 2012),
    "zák. o obch. korporacích": (90, 2012),
    # Civil Procedure
    "o. s. ř.": (99, 1963),
    "o.s.ř.": (99, 1963),
    # Criminal Procedure
    "tr. ř.": (141, 1961),
    "tr.ř.": (141, 1961),
    "trestního řádu": (141, 1961),
    # Administrative Procedure
    "s. ř. s.": (150, 2002),
    "správního řádu": (500, 2004),
    "spr. řádu": (500, 2004),
    # Insolvency
    "insolv. zákona": (182, 2006),
    "insolvenčního zákona": (182, 2006),
}


# ---------------------------------------------------------------------------
# HTML parsers
# ---------------------------------------------------------------------------


def parse_search_results(html: str) -> list[dict]:
    """Parse the search results list page.

    Each result row contains: case_number, category, legal_thesis,
    source_unid (from the link/checkbox), and source_url.

    Parameters
    ----------
    html : str
        Full HTML of a ``$$WebSearch1`` results page.

    Returns
    -------
    list[dict]
        List of decision metadata dicts (suitable for upsert after enrichment).
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for row in soup.select("tr"):
        link = row.select_one("a.odk")
        if not link:
            continue

        href = link.get("href", "")
        unid_match = re.search(r"/WebSearch/([A-F0-9]{32})\?", href, re.I)
        if not unid_match:
            continue
        unid = unid_match.group(1).upper()

        case_number = link.get_text(strip=True)
        cells = row.find_all("td")

        category = ""
        legal_thesis = ""

        for cell in cells:
            cls = " ".join(cell.get("class", []))
            if "category" in cls:
                category = cell.get_text(strip=True)
            elif "td-long" in cls:
                legal_thesis = _clean_text(cell.get_text(" ", strip=True))

        if not case_number or not unid:
            continue

        results.append(
            {
                "source_unid": unid,
                "case_number": case_number,
                "category": category or None,
                "legal_thesis": legal_thesis or None,
                "source_url": f"{_BASE}/Judikatura/judikatura_ns.nsf/WebSearch/{unid}?openDocument",
                # ECLI is not available in list pages — synthesized from UNID as placeholder
                # until the individual metadata page is fetched.
                "ecli": f"NSOUD:{unid}",
                "court": "Nejvyssi soud",
            }
        )

    return results


def parse_decision_page(html: str) -> dict:
    """Parse an individual decision metadata page.

    Extracts: ECLI, decision_date, decision_type, judges (from Soud),
    keywords (Heslo), statute references (Dotčené předpisy), and
    full Anotace text.

    Parameters
    ----------
    html : str
        Full HTML of a decision page (``/WebSearch/{UNID}?openDocument``).

    Returns
    -------
    dict
        Enrichment data to merge into the existing record via upsert.
    """
    soup = BeautifulSoup(html, "html.parser")
    data: dict = {}

    # Parse the metadata table — rows are label/value pairs
    table = soup.select_one(".table-wrapper table")
    if not table:
        return data

    label_map: dict[str, str] = {}
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) >= 2:
            label = cells[0].get_text(strip=True).rstrip(":")
            value = cells[1].get_text(" ", strip=True)
            label_map[label] = value

    # ECLI
    ecli_raw = label_map.get("ECLI", "").strip()
    if ecli_raw.startswith("ECLI:"):
        data["ecli"] = ecli_raw

    # Decision date — Czech format "18. 9. 2024" → date(2024, 9, 18)
    date_raw = label_map.get("Datum rozhodnutí", "").strip()
    if date_raw:
        parsed_date = _parse_czech_date(date_raw)
        if parsed_date:
            data["decision_date"] = parsed_date

    # Decision type
    typ_raw = label_map.get("Typ rozhodnutí", "").strip().lower()
    if typ_raw:
        if "rozsudek" in typ_raw:
            data["decision_type"] = "rozsudek"
        elif "usnesení" in typ_raw or "usneseni" in typ_raw:
            data["decision_type"] = "usneseni"
        else:
            data["decision_type"] = typ_raw

    # Category
    cat_raw = label_map.get("Kategorie rozhodnutí", "").strip()
    if cat_raw:
        data["category"] = cat_raw[0] if cat_raw else None  # first char e.g. "A"

    # Keywords (Heslo — space-separated combined value)
    heslo_raw = label_map.get("Heslo", "").strip()
    if heslo_raw:
        # Keywords appear concatenated without separator; split on CamelCase/capitals
        keywords = [k.strip() for k in re.split(r"\s{2,}|\n", heslo_raw) if k.strip()]
        if keywords:
            data["keywords"] = keywords

    # Statute references (Dotčené předpisy)
    dotcene_raw = label_map.get("Dotčené předpisy", "").strip()
    if dotcene_raw:
        data["regulations"] = _extract_regulations_from_dotcene(dotcene_raw)

    # Legal thesis (Právní věta) — may be longer on individual page
    pv_raw = label_map.get("Právní věta", "").strip()
    if pv_raw:
        data["legal_thesis"] = _clean_text(pv_raw)

    # Full text = Anotace (summary/reasoning annotation)
    anotace_raw = label_map.get("Anotace", "").strip()
    if anotace_raw:
        data["full_text"] = _clean_text(anotace_raw)
        data["full_text_fetched"] = True

    return data


def _extract_regulations_from_dotcene(text: str) -> list[dict]:
    """Parse 'Dotčené předpisy' raw text into structured regulation objects.

    Input example:
        "§ 13 tr. zákoníku§ 16 tr. zákoníku§ 22 odst. 1 tr. zákoníku"

    Output:
        [{"paragraph": "13", "law_number": 40, "law_year": 2009}, ...]
    """
    results = []
    seen: set[tuple] = set()

    # Split on § signs that are not at the start
    items = re.split(r"(?=§)", text)
    for item in items:
        item = item.strip()
        if not item:
            continue

        # Extract paragraph: §NN or § NN odst. X pism. Y etc.
        par_match = re.match(
            r"§\s*(\d[\w\s]*?)(?:\s+(?:odst|písm|al)\b.*?)?(?:\s+(?:tr\.|obč\.|o\.|z\.|zákoník|zákon)|$)", item, re.I
        )
        if not par_match:
            continue
        paragraph = par_match.group(1).strip()

        # Find law abbreviation in item text
        law_number, law_year = _match_law_abbreviation(item)
        if not law_number:
            continue

        key = (paragraph, law_number, law_year)
        if key not in seen:
            seen.add(key)
            results.append({"paragraph": paragraph, "law_number": law_number, "law_year": law_year})

    return results


def extract_regulations(text: str) -> list[dict]:
    """Extract statute references from Czech legal text using regex.

    Handles patterns:
    - "z. č. NNN/YYYY Sb." with optional "§ NN"
    - "zákon č. NNN/YYYY" with optional "§ NN"
    - Abbreviated law names: "§ 52 zákoníku práce", "§ 13 tr. zákoníku"

    Parameters
    ----------
    text : str
        Czech legal text (legal thesis, keywords, or reasoning).

    Returns
    -------
    list[dict]
        ``[{"paragraph": "52", "law_number": 262, "law_year": 2006}, ...]``
    """
    results = []
    seen: set[tuple] = set()

    # Pattern 1: "z. č. NNN/YYYY Sb." or "zákona č. NNN/YYYY"
    official_pat = re.compile(
        r"(?:zákon|z\.)\s*č\.?\s*(\d{1,4})/(\d{4})\s*Sb\.?",
        re.I,
    )
    for m in official_pat.finditer(text):
        law_number = int(m.group(1))
        law_year = int(m.group(2))
        # Look for § N before the match (within 50 chars)
        pre = text[max(0, m.start() - 50) : m.start()]
        par_m = re.search(r"§\s*(\d+\w?)", pre)
        paragraph = par_m.group(1) if par_m else ""
        key = (paragraph, law_number, law_year)
        if key not in seen:
            seen.add(key)
            results.append({"paragraph": paragraph, "law_number": law_number, "law_year": law_year})

    # Pattern 2: "§ NN <law_abbrev>" — abbreviated law names.
    # Strategy: find every § NN occurrence, then scan a 80-char window after it
    # for known law abbreviations.  A window approach avoids false negatives
    # from lazy-quantifier max-length limits when the text after § is long.
    par_pat = re.compile(r"§\s*(\d+\w?)", re.I)
    for m in par_pat.finditer(text):
        paragraph = m.group(1)
        # Context window: up to 80 chars after the § NN token
        window = text[m.start() : m.start() + 80]
        law_number, law_year = _match_law_abbreviation(window)
        if not law_number:
            continue
        key = (paragraph, law_number, law_year)
        if key not in seen:
            seen.add(key)
            results.append({"paragraph": paragraph, "law_number": law_number, "law_year": law_year})

    return results


def _match_law_abbreviation(text: str) -> tuple[int, int]:
    """Match abbreviated law name in text, returning (law_number, law_year) or (0, 0).

    When multiple abbreviations match, returns the one that appears earliest
    (lowest character offset) in ``text``.  This prevents a later abbreviation
    in a 80-char window from overriding the intended one that appears first.
    """
    text_lower = text.lower()
    best_pos = len(text)
    best_result = (0, 0)
    for abbrev, (num, yr) in _LAW_ABBREV.items():
        pos = text_lower.find(abbrev.lower())
        if pos != -1 and pos < best_pos:
            best_pos = pos
            best_result = (num, yr)
    return best_result


def _parse_czech_date(text: str) -> date | None:
    """Parse Czech date format '18. 9. 2024' → date(2024, 9, 18)."""
    text = text.strip()
    m = re.match(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    # Try ISO format
    m2 = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m2:
        try:
            return date(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
        except ValueError:
            return None
    return None


def _clean_text(text: str) -> str:
    """Normalize whitespace in extracted text."""
    return re.sub(r"[ \t]{2,}", " ", text).strip()


# ---------------------------------------------------------------------------
# Scraper engine
# ---------------------------------------------------------------------------


async def _retry_get(client: httpx.AsyncClient, url: str, *, retries: int = _MAX_RETRIES) -> httpx.Response:
    """GET with exponential backoff retry."""
    delay = 1.0
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_exc = exc
            logger.warning("[scraper] GET %s failed (attempt %d/%d): %s", url[:80], attempt + 1, retries, exc)
            if attempt < retries - 1:
                await asyncio.sleep(delay)
                delay *= 2
    raise RuntimeError(f"GET {url} failed after {retries} attempts") from last_exc


async def _retry_post(
    client: httpx.AsyncClient,
    url: str,
    data: dict,
    *,
    retries: int = _MAX_RETRIES,
) -> httpx.Response:
    """POST with exponential backoff retry."""
    delay = 1.0
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = await client.post(url, data=data, follow_redirects=True)
            resp.raise_for_status()
            return resp
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            last_exc = exc
            logger.warning("[scraper] POST %s failed (attempt %d/%d): %s", url[:80], attempt + 1, retries, exc)
            if attempt < retries - 1:
                await asyncio.sleep(delay)
                delay *= 2
    raise RuntimeError(f"POST {url} failed after {retries} attempts") from last_exc


async def _build_search_url(
    client: httpx.AsyncClient,
    date_from: date,
    date_to: date,
) -> str:
    """Submit the search form and return the Domino query URL for pagination.

    Returns the base URL without Start/Count so we can append them for each page.
    """
    form_date_from = date_from.strftime("%d.%m.%Y")
    form_date_to = date_to.strftime("%d.%m.%Y")
    resp = await _retry_post(
        client,
        _SEARCH_URL,
        {
            "od": form_date_from,
            "do": form_date_to,
            "dateod": form_date_from,
            "datedo": form_date_to,
        },
    )
    # Domino redirects POST to a GET URL containing the encoded Domino query
    final_url = str(resp.url)
    # The redirect URL already has URL-encoded query params.
    # Do NOT re-parse and re-encode — that causes double-encoding (%5B → %255B).
    # Instead, strip Start= / Count= / SearchMax= with simple string surgery
    # and keep all other parameters intact at their original encoding level.
    base_url = re.sub(r"&?(Start|Count|SearchMax)=[^&]*", "", final_url).rstrip("?&")
    return base_url


async def search_by_year(
    year: int,
    client: httpx.AsyncClient,
) -> list[dict]:
    """Download all decisions for a given year by paginating through search results.

    Uses the search form POST → redirect → GET pagination pattern.
    Rate limited to ``_REQUEST_DELAY_S`` between page fetches.

    Parameters
    ----------
    year : int
        Calendar year to search.
    client : httpx.AsyncClient
        Shared HTTP client.

    Returns
    -------
    list[dict]
        Parsed decision metadata from all list pages (no individual page visits).
    """
    date_from = date(year, 1, 1)
    date_to = date(year, 12, 31)
    # Cap date_to at today
    today = datetime.now(UTC).date()
    if date_to > today:
        date_to = today

    logger.info("[scraper] searching year %d (%s – %s)", year, date_from, date_to)

    base_url = await _build_search_url(client, date_from, date_to)
    await asyncio.sleep(_REQUEST_DELAY_S)

    all_results: list[dict] = []
    start = 0

    while True:
        page_url = f"{base_url}&Start={start}&Count={_PAGE_SIZE}"
        resp = await _retry_get(client, page_url)
        await asyncio.sleep(_REQUEST_DELAY_S)

        page_results = parse_search_results(resp.text)
        if not page_results:
            break

        all_results.extend(page_results)
        logger.info(
            "[scraper] year %d: page start=%d → %d decisions (total=%d)",
            year,
            start,
            len(page_results),
            len(all_results),
        )

        if len(page_results) < _PAGE_SIZE:
            break  # Last (partial) page
        start += _PAGE_SIZE

    logger.info("[scraper] year %d: %d total decisions found", year, len(all_results))
    return all_results


async def fetch_decision(
    unid: str,
    client: httpx.AsyncClient,
) -> dict:
    """Fetch individual decision metadata page and return parsed enrichment data.

    Parameters
    ----------
    unid : str
        Domino UNID (32-char hex string).
    client : httpx.AsyncClient
        Shared HTTP client.

    Returns
    -------
    dict
        Metadata dict suitable for merging into an existing record.
    """
    url = _DECISION_URL.format(unid=unid)
    resp = await _retry_get(client, url)
    return parse_decision_page(resp.text)


async def _fetch_and_enrich(
    record: dict,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Fetch individual page for a record and merge enrichment data."""
    async with semaphore:
        try:
            enrichment = await fetch_decision(record["source_unid"], client)
            await asyncio.sleep(_REQUEST_DELAY_S)
        except Exception as exc:
            logger.warning("[scraper] failed to enrich %s: %s", record.get("case_number"), exc)
            enrichment = {}
    return {**record, **enrichment}


# ---------------------------------------------------------------------------
# CLI modes
# ---------------------------------------------------------------------------


async def run_bulk(
    from_year: int,
    to_year: int,
    *,
    enrich: bool = True,
    concurrency: int = 5,
) -> None:
    """Download all decisions for a year range and store in DB.

    Parameters
    ----------
    from_year, to_year : int
        Year range (inclusive).
    enrich : bool
        If True, also fetch individual metadata pages for ECLI, date, type, etc.
        This is slower but produces complete records.  Set False to only store
        list-page data (faster, but ECLI is a synthetic key).
    concurrency : int
        Number of concurrent individual-page fetches during enrichment.
    """
    from neolex.db.court_decisions import get_decisions_count, upsert_decision

    async with httpx.AsyncClient(headers=_HEADERS, timeout=30, follow_redirects=True) as client:
        total_new = 0
        total_errors = 0

        for year in range(from_year, to_year + 1):
            try:
                year_results = await search_by_year(year, client)
            except Exception as exc:
                logger.error("[scraper] year %d search failed: %s", year, exc)
                total_errors += 1
                continue

            if not year_results:
                logger.info("[scraper] year %d: no results", year)
                continue

            # Optionally enrich with individual page data
            if enrich:
                logger.info(
                    "[scraper] year %d: enriching %d decisions (concurrency=%d)...",
                    year,
                    len(year_results),
                    concurrency,
                )
                semaphore = asyncio.Semaphore(concurrency)
                year_results = await asyncio.gather(*[_fetch_and_enrich(r, client, semaphore) for r in year_results])

            # Upsert all records
            for record in year_results:
                try:
                    await upsert_decision(record)
                    total_new += 1
                except Exception as exc:
                    logger.warning("[scraper] upsert failed for %s: %s", record.get("case_number"), exc)
                    total_errors += 1

            count = await get_decisions_count()
            logger.info("[scraper] year %d done. DB total: %d", year, count)

    logger.info(
        "[scraper] bulk complete: %d upserted, %d errors",
        total_new,
        total_errors,
    )


async def run_sync(days: int = 7) -> None:
    """Download decisions from the last N days and upsert to DB.

    Always fetches individual pages for complete metadata including ECLI.
    """
    from neolex.db.court_decisions import upsert_decision

    today = datetime.now(UTC).date()
    date_from = today - timedelta(days=days)

    logger.info("[scraper] sync: fetching decisions from %s to %s", date_from, today)

    async with httpx.AsyncClient(headers=_HEADERS, timeout=30, follow_redirects=True) as client:
        base_url = await _build_search_url(client, date_from, today)
        await asyncio.sleep(_REQUEST_DELAY_S)

        all_results: list[dict] = []
        start = 0
        while True:
            page_url = f"{base_url}&Start={start}&Count={_PAGE_SIZE}"
            resp = await _retry_get(client, page_url)
            await asyncio.sleep(_REQUEST_DELAY_S)
            page_results = parse_search_results(resp.text)
            if not page_results:
                break
            all_results.extend(page_results)
            if len(page_results) < _PAGE_SIZE:
                break
            start += _PAGE_SIZE

        logger.info("[scraper] sync: found %d decisions, enriching...", len(all_results))
        semaphore = asyncio.Semaphore(3)
        all_results = list(await asyncio.gather(*[_fetch_and_enrich(r, client, semaphore) for r in all_results]))

        new_count = 0
        err_count = 0
        for record in all_results:
            try:
                await upsert_decision(record)
                new_count += 1
            except Exception as exc:
                logger.warning("[scraper] sync upsert failed for %s: %s", record.get("case_number"), exc)
                err_count += 1

    logger.info("[scraper] sync complete: %d upserted, %d errors", new_count, err_count)


async def run_fetch_text(ecli: str) -> None:
    """Fetch full text for a specific decision by ECLI and cache in DB."""
    from neolex.db.court_decisions import get_decision_by_ecli, upsert_decision

    record = await get_decision_by_ecli(ecli)
    if not record:
        logger.error("[scraper] ECLI not found: %s", ecli)
        return

    if record.full_text_fetched:
        logger.info("[scraper] full text already cached for %s", ecli)
        return

    unid = record.source_unid
    if not unid:
        logger.error("[scraper] no source_unid for %s — cannot fetch", ecli)
        return

    async with httpx.AsyncClient(headers=_HEADERS, timeout=30, follow_redirects=True) as client:
        enrichment = await fetch_decision(unid, client)

    if enrichment.get("full_text"):
        await upsert_decision(
            {
                "ecli": ecli,
                "case_number": record.case_number,
                "full_text": enrichment["full_text"],
                "full_text_fetched": True,
            }
        )
        logger.info("[scraper] full text cached for %s (%d chars)", ecli, len(enrichment["full_text"]))
    else:
        logger.warning("[scraper] no full text found for %s", ecli)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Czech Supreme Court decision scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python scripts/scrape_supreme_court.py --mode bulk --from-year 2010 --to-year 2026
  uv run python scripts/scrape_supreme_court.py --mode sync --days 7
  uv run python scripts/scrape_supreme_court.py --mode fetch-text --ecli ECLI:CZ:NS:2024:4.TDO.621.2024.1
  uv run python scripts/scrape_supreme_court.py --mode bulk --from-year 2025 --no-enrich
""",
    )
    parser.add_argument(
        "--mode",
        choices=["bulk", "sync", "fetch-text"],
        required=True,
        help="Operation mode",
    )
    parser.add_argument("--from-year", type=int, default=2010, help="Start year for bulk mode")
    parser.add_argument("--to-year", type=int, default=datetime.now(UTC).year, help="End year for bulk mode")
    parser.add_argument("--days", type=int, default=7, help="Days to look back in sync mode")
    parser.add_argument("--ecli", type=str, default="", help="ECLI for fetch-text mode")
    parser.add_argument(
        "--no-enrich",
        action="store_true",
        help="Bulk mode: skip individual page fetches (faster but ECLI is synthetic)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Concurrent individual page fetches during enrichment (default: 5)",
    )
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.mode == "bulk":
        asyncio.run(
            run_bulk(
                args.from_year,
                args.to_year,
                enrich=not args.no_enrich,
                concurrency=args.concurrency,
            )
        )
    elif args.mode == "sync":
        asyncio.run(run_sync(days=args.days))
    elif args.mode == "fetch-text":
        if not args.ecli:
            parser.error("--ecli is required for fetch-text mode")
        asyncio.run(run_fetch_text(args.ecli))


if __name__ == "__main__":
    main()
