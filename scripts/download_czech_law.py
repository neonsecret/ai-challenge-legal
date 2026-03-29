#!/usr/bin/env python3
"""Download key Czech legislation from zakonyprolidi.cz and save as plain text.

Usage:
    python3 scripts/download_czech_law.py

Output: data/corpus/czech/<law_id>.txt  (one file per law)
"""
from __future__ import annotations

import re
import time
import logging
from pathlib import Path
from html.parser import HTMLParser

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/corpus/czech")

# Key Czech codes: (law_id, short_name)
LAWS = [
    ("2012-89", "obcansky_zakonik"),  # Civil Code
    ("2009-40", "trestni_zakonik"),  # Criminal Code
    ("2006-262", "zakonik_prace"),  # Labour Code
    ("2012-90", "zakon_obch_korporace"),  # Business Corporations Act
    ("2004-500", "spravni_rad"),  # Administrative Procedure Code
    ("1991-455", "zivnostensky_zakon"),  # Trade Licensing Act (Živnostenský zákon)
    ("1995-155", "zakon_duchodove_pojisteni"),  # Pension Insurance Act
    ("2004-235", "zakon_dph"),  # VAT Act (DPH)
    ("1992-586", "zakon_dane_prijmu"),  # Income Tax Act
    ("2006-187", "zakon_nemocenske_pojisteni"),  # Sickness Insurance Act
    ("2009-280", "danovy_rad"),  # Tax Procedure Code (Daňový řád)
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)",
    "Accept-Language": "cs,en;q=0.9",
}


class LawTextExtractor(HTMLParser):
    """Extract law paragraph text from zakonyprolidi.cz HTML."""

    SKIP_TAGS = {"script", "style", "nav", "header", "footer", "iframe"}
    # These IDs/classes contain the law body on zakonyprolidi.cz
    CONTENT_ATTRS = {"id": {"predpis", "content-predpis"}, "class": {"predpis"}}

    def __init__(self) -> None:
        super().__init__()
        self.in_content = False
        self.content_depth = 0
        self.skip_depth = 0
        self.fragments: list[str] = []
        self._tag_stack: list[str] = []

    def _is_content_tag(self, attrs: list) -> bool:
        attr_dict = dict(attrs)
        tag_id = attr_dict.get("id", "")
        tag_class = attr_dict.get("class", "")
        return (
                tag_id in ("predpis", "content-predpis", "law-body", "law-text")
                or "predpis" in tag_class
                or "law-body" in tag_class
        )

    def handle_starttag(self, tag: str, attrs) -> None:
        self._tag_stack.append(tag)
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if not self.in_content and self._is_content_tag(attrs):
            self.in_content = True
            self.content_depth = len(self._tag_stack)

    def handle_endtag(self, tag: str) -> None:
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
        if tag in self.SKIP_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1
            return
        if self.in_content and len(self._tag_stack) < self.content_depth:
            self.in_content = False

    def handle_data(self, data: str) -> None:
        if self.skip_depth > 0:
            return
        text = data.strip()
        if text:
            self.fragments.append(text)

    def get_text(self) -> str:
        return "\n".join(self.fragments)


def download_law(law_id: str, short_name: str) -> str | None:
    """Download a law and return its plain text, or None on failure."""
    url = f"https://www.zakonyprolidi.cz/cs/{law_id}"
    logger.info("Downloading %s (%s) ...", short_name, url)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error("Failed to download %s: %s", law_id, e)
        return None

    html = resp.text
    # Try to find the law content — zakonyprolidi.cz embeds it inline
    # Look for the section between "§ 1" style markers
    # Strategy 1: use the parser
    parser = LawTextExtractor()
    parser.feed(html)
    text = parser.get_text()

    # Strategy 2: if parser found almost nothing, extract raw text via regex
    if len(text) < 5000:
        logger.warning("Parser found only %d chars for %s, falling back to regex", len(text), short_name)
        # Strip tags
        raw = re.sub(r"<[^>]+>", " ", html)
        raw = re.sub(r"\s+", " ", raw)
        # Find the section from the law start
        m = re.search(r"(ZÁKON\s+ze dne|§\s*1\s*\(1\))", raw)
        if m:
            text = raw[m.start():]
        else:
            text = raw

    # Clean up the text
    lines = [ln.strip() for ln in text.splitlines()]
    # Remove duplicate blank lines
    cleaned: list[str] = []
    prev_blank = False
    for ln in lines:
        is_blank = len(ln) == 0
        if is_blank and prev_blank:
            continue
        cleaned.append(ln)
        prev_blank = is_blank

    return "\n".join(cleaned)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for law_id, short_name in LAWS:
        out_path = OUTPUT_DIR / f"{short_name}.txt"
        if out_path.exists() and out_path.stat().st_size > 10_000:
            logger.info("Already have %s (%d bytes), skipping.", short_name, out_path.stat().st_size)
            continue

        text = download_law(law_id, short_name)
        if text:
            out_path.write_text(text, encoding="utf-8")
            logger.info("Saved %s → %s (%d chars)", short_name, out_path, len(text))
        else:
            logger.error("Failed to get text for %s", short_name)

        time.sleep(2)  # polite delay


if __name__ == "__main__":
    main()
