"""Proxy endpoint for fetching and extracting readable text from web pages.

Used by the frontend grounding panel to display web search result previews.
Fetches pages server-side to avoid CORS issues and extracts main content
using BeautifulSoup (available as a transitive dependency via docling).
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
import time
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from neolex.auth.middleware import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/proxy")

# Simple in-memory cache: url -> (timestamp, result_dict)
# Design decision: the cache is keyed by URL only (not per-user) because this
# proxy is exclusively for public web search result pages.  The endpoint is
# auth-gated, so only authenticated users can reach it, and we validate that
# URLs are public (no private IPs).  URLs that contain authentication tokens in
# query parameters are never cached (see _url_has_auth_params below).
_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes
_CACHE_MAX_SIZE = 50
_CONTENT_MAX_CHARS = 10_000
_FETCH_TIMEOUT_SECONDS = 10

# Query-parameter names that suggest the URL carries authentication material.
# URLs matching these are fetched but never cached to avoid leaking tokens to
# other users.
_AUTH_PARAM_NAMES = frozenset({"token", "key", "secret", "password", "api_key", "apikey", "access_token"})


def _url_has_auth_params(url: str) -> bool:
    """Return True if the URL query string contains likely auth tokens."""
    parsed = urlparse(url)
    if not parsed.query:
        return False
    # Parse query params (lowercase keys for case-insensitive matching)
    for part in parsed.query.split("&"):
        name = part.split("=", 1)[0].lower()
        if name in _AUTH_PARAM_NAMES:
            return True
    return False


def _is_private_ip(hostname: str) -> bool:
    """Check if a hostname resolves to a private/reserved IP address.

    Handles IPv4, IPv6 (including ``::1``, ``fe80::`` link-local, and
    IPv4-mapped ``::ffff:127.0.0.1``), and common private domain names.
    Strips ``[]`` brackets from IPv6 literal hostnames before parsing.
    """
    try:
        addr = ipaddress.ip_address(hostname.strip("[]"))
        return (addr.is_private or addr.is_reserved or addr.is_loopback
                or addr.is_link_local or addr.is_multicast)
    except ValueError:
        # Not a raw IP — could be a domain name. We check common private patterns.
        lower = hostname.lower().strip("[]")
        return lower in ("localhost",) or lower.endswith(".local") or lower.endswith(".internal")


def _validate_url(url: str) -> str:
    """Validate and normalize a URL. Raises HTTPException on invalid input."""
    if not url or len(url) > 2048:
        raise HTTPException(status_code=400, detail="Invalid URL")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Only http/https URLs are allowed")

    hostname = parsed.hostname or ""
    if not hostname:
        raise HTTPException(status_code=400, detail="Invalid URL: no hostname")

    if _is_private_ip(hostname):
        raise HTTPException(status_code=400, detail="Private/local URLs are not allowed")

    # DNS resolution check: resolve hostname and verify all IPs are public
    # to prevent SSRF via DNS rebinding or domains pointing to internal IPs.
    #
    # Accepted residual risk (TOCTOU): A DNS record could change between this
    # check and the actual HTTP connection. This is acceptable because:
    #   1. The endpoint is auth-gated — only paying/authenticated users can reach it.
    #   2. Redirect targets are also validated via _validate_url(), closing the
    #      most common SSRF bypass.
    #   3. The timing window is extremely narrow (milliseconds).
    #   4. Exploiting this would require the attacker to control a DNS server
    #      and time the rebind precisely during the request.
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise HTTPException(status_code=400, detail="Could not resolve hostname")
    for info in infos:
        ip = info[4][0]
        if _is_private_ip(ip):
            raise HTTPException(status_code=400, detail="Private/local URLs are not allowed")

    return url


def _is_link_heavy(tag) -> bool:
    """Return True if a tag's text is >50% composed of link text (navigation/archive)."""
    total_text = tag.get_text(strip=True)
    if len(total_text) < 50:
        return False
    link_text = "".join(a.get_text(strip=True) for a in tag.find_all("a"))
    return len(link_text) > len(total_text) * 0.5


def _collapse_repetitive_lines(text: str) -> str:
    """Collapse consecutive lines that follow a repetitive pattern.

    Detects runs of 4+ lines matching patterns like "N. čtvrtletí YYYY" or
    similar dated archive listings and replaces them with a short summary.
    """
    lines = text.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        # Look for runs of short, structurally similar lines (likely archive links)
        run_start = i
        # A "repetitive" line: short (<80 chars), contains a year (4 digits)
        while (
            i < len(lines)
            and len(lines[i].strip()) < 80
            and re.search(r"\b(19|20)\d{2}\b", lines[i])
            and lines[i].strip()
        ):
            i += 1
        run_length = i - run_start
        if run_length >= 4:
            # Collapse the run
            result.append(f"[{run_length} archive entries omitted]")
        else:
            # Not a run — emit lines normally
            for j in range(run_start, i):
                result.append(lines[j])
            if i < len(lines):
                result.append(lines[i])
                i += 1
            continue
    return "\n".join(result)


# CSS class/id patterns that indicate non-content elements
_JUNK_CLASS_PATTERNS = re.compile(
    r"sidebar|menu|breadcrumb|pagination|related|archive|social|cookie|newsletter|"
    r"subscribe|signup|sign-up|promo|banner|popup|modal|comment|share|widget|"
    r"toolbar|masthead|topbar|bottombar",
    re.IGNORECASE,
)


def _extract_text_bs4(html: str) -> tuple[str, str]:
    """Extract readable text and title from HTML using BeautifulSoup.

    Returns (title, content) tuple.
    """
    try:
        from bs4 import BeautifulSoup, Tag

        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)

        # 1. Remove script, style, nav, footer, header, aside, noscript tags
        for tag in soup.find_all(
            ["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe", "svg"]
        ):
            tag.decompose()

        # 2. Remove elements with ARIA roles that indicate non-content
        for role in ("navigation", "complementary", "contentinfo", "banner", "search"):
            for tag in soup.find_all(attrs={"role": role}):
                tag.decompose()

        # 3. Remove elements whose class or id matches junk patterns.
        # Collect matching tags first, then decompose — avoids AttributeError
        # when a decomposed parent invalidates child tags still in the iterator.
        junk_tags = []
        for tag in soup.find_all(True):
            if not isinstance(tag, Tag):
                continue
            if tag.attrs is None:
                continue
            classes = " ".join(tag.get("class", []))
            tag_id = tag.get("id", "") or ""
            if _JUNK_CLASS_PATTERNS.search(classes) or _JUNK_CLASS_PATTERNS.search(tag_id):
                junk_tags.append(tag)
        for tag in junk_tags:
            tag.decompose()

        # 4. Remove link-heavy block elements (likely nav/archive listings)
        for tag in soup.find_all(["div", "section", "ul", "ol"]):
            if isinstance(tag, Tag) and _is_link_heavy(tag):
                tag.decompose()

        # 5. Find main content area with better scoring
        content_root = None

        # Prefer <article> first (most specific), then <main>, then [role=main]
        content_root = soup.find("article") or soup.find("main") or soup.find(attrs={"role": "main"})

        if not content_root:
            # Heuristic: find the div with the most direct text content
            body = soup.find("body") or soup
            best_div = None
            best_text_len = 0
            for div in body.find_all("div", recursive=True):
                if not isinstance(div, Tag):
                    continue
                # Get direct text length (excluding nested divs' text to avoid
                # always picking the outermost wrapper)
                direct_text = div.find_all(string=True, recursive=False)
                p_text = "".join(
                    p.get_text(strip=True) for p in div.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "blockquote"])
                )
                text_len = len(p_text) + sum(len(t.strip()) for t in direct_text)
                if text_len > best_text_len:
                    best_text_len = text_len
                    best_div = div

            if best_div and best_text_len > 200:
                content_root = best_div
            else:
                content_root = body

        text = content_root.get_text(separator="\n", strip=True)

        # 6. Clean up excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)

        # 7. Collapse repetitive archive-style line runs
        text = _collapse_repetitive_lines(text)

        # 8. Final cleanup of any blank line runs introduced by collapsing
        text = re.sub(r"\n{3,}", "\n\n", text)

        return title, text.strip()
    except ImportError:
        # bs4 not available — fall back to regex stripping
        return _extract_text_regex(html)


def _extract_text_regex(html: str) -> tuple[str, str]:
    """Fallback text extraction using regex when bs4 is unavailable."""
    # Extract title
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""

    # Strip tags
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    return title, text.strip()


def _evict_cache() -> None:
    """Evict expired entries and trim to max size."""
    now = time.monotonic()
    expired = [k for k, (ts, _) in _cache.items() if now - ts > _CACHE_TTL_SECONDS]
    for k in expired:
        del _cache[k]

    # If still over limit, remove oldest entries
    if len(_cache) > _CACHE_MAX_SIZE:
        by_age = sorted(_cache.items(), key=lambda x: x[1][0])
        for k, _ in by_age[: len(_cache) - _CACHE_MAX_SIZE]:
            del _cache[k]


@router.get("/web-content")
async def proxy_web_content(
    url: str = Query(..., description="URL to fetch and extract content from"),
    key_row: dict = Depends(get_api_key),
):
    """Fetch a web page and return extracted readable text content.

    Used by the frontend grounding panel for web source previews.
    Requires authentication via session cookie.
    """
    url = _validate_url(url)
    skip_cache = _url_has_auth_params(url)

    # Check cache (skip for URLs that contain auth tokens)
    now = time.monotonic()
    if not skip_cache and url in _cache:
        ts, cached_result = _cache[url]
        if now - ts < _CACHE_TTL_SECONDS:
            return cached_result

    # Fetch the page (redirects disabled to prevent SSRF redirect bypass)
    _MAX_REDIRECTS = 5
    try:
        async with httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT_SECONDS,
            follow_redirects=False,
        ) as client:
            _headers = {
                "User-Agent": "Mozilla/5.0 (compatible; VitreonBot/1.0)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            response = await client.get(url, headers=_headers)

            # Manually follow redirects with URL validation
            for _ in range(_MAX_REDIRECTS):
                if response.status_code not in (301, 302, 303, 307, 308):
                    break
                redirect_url = response.headers.get("location")
                if not redirect_url:
                    break
                # Resolve relative redirects
                if redirect_url.startswith("/"):
                    parsed_orig = urlparse(url)
                    redirect_url = f"{parsed_orig.scheme}://{parsed_orig.netloc}{redirect_url}"
                # Validate the redirect target against SSRF rules
                redirect_url = _validate_url(redirect_url)
                response = await client.get(redirect_url, headers=_headers)

            response.raise_for_status()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timed out fetching the page")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Remote server returned {e.response.status_code}")
    except httpx.HTTPError as e:
        logger.warning("[web-proxy] fetch failed for %s: %s", url[:80], e)
        raise HTTPException(status_code=502, detail="Failed to fetch the page")

    # Check content type — only process HTML
    content_type = response.headers.get("content-type", "")
    if "html" not in content_type.lower() and "xml" not in content_type.lower():
        raise HTTPException(status_code=400, detail="URL does not point to an HTML page")

    # Guard against oversized responses to prevent memory exhaustion.
    # Check Content-Length header first (fast path), then verify actual body size.
    MAX_HTML_BYTES = 5 * 1024 * 1024  # 5 MB
    content_length = response.headers.get("content-length")
    if content_length and int(content_length) > MAX_HTML_BYTES:
        raise HTTPException(status_code=400, detail="Page too large to process")
    raw_bytes = response.content  # httpx loads content; check size after
    if len(raw_bytes) > MAX_HTML_BYTES:
        raise HTTPException(status_code=400, detail="Page too large to process")
    html = raw_bytes.decode(response.encoding or "utf-8", errors="replace")
    title, content = _extract_text_bs4(html)

    # Truncate content to limit
    if len(content) > _CONTENT_MAX_CHARS:
        content = content[:_CONTENT_MAX_CHARS] + "\n\n[Content truncated]"

    result = {
        "url": url,
        "title": title or urlparse(url).hostname or "",
        "content": content,
    }

    # Cache the result (skip for URLs carrying auth tokens)
    if not skip_cache:
        _evict_cache()
        _cache[url] = (now, result)

    return result
