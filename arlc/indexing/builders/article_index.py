"""Build article-to-page reverse index for all DIFC legal documents.

Scans all 30 PDFs in data/documents/ and extracts:
1. Article N → page number(s) mapping for laws/regulations
2. Rule N → page number(s) mapping for court rules
3. Section N → page number(s) mapping
4. Document type classification (LAW, CASE, REGULATION)
5. Court case structure: ORDER/last pages, date-of-issue page

Output: data/article_page_index.json
"""

import json
import os
import re

import pymupdf

DOCS_DIR = "data/documents"
DOCLING_DIR = "data/documents_md"
OUTPUT = "data/article_page_index.json"

# Docling-based article extraction inspired by guy3 (structure-first) and guy1 (typed ontology)

# Map Docling heading prefixes to article_page_index key prefixes
_DOCLING_HEADING_RE = re.compile(
    r'^(Article|ARTICLE)\s+(\d+[A-Z]?(?:\(\d+\))?)'
    r'|^(Section|SECTION)\s+(\d+[A-Z]?)'
    r'|^(Rule|RULE)\s+(\d+[A-Z]?)'
    r'|^(Regulation|REGULATION)\s+(\d+(?:\.\d+)?)'
    r'|^(Schedule|SCHEDULE)\s+(\d+)'
    r'|^(Part|PART)\s+([\dIVXLivxl]+)'
    r'|^(Appendix|APPENDIX)\s+(\d+)'
    r'|^(Chapter|CHAPTER)\s+([\dIVXLivxl]+)',
    re.IGNORECASE
)


def _heading_to_key(heading: str) -> str | None:
    """Convert a Docling section heading to an article_page_index key.

    E.g. "Article 28" -> "article_28", "Schedule 3" -> "schedule_3",
         "Article 5(1)" -> "article_5_sub_1"
    """
    m = _DOCLING_HEADING_RE.match(heading.strip())
    if not m:
        return None
    # Find which group matched (pairs of prefix, number)
    groups = m.groups()
    for i in range(0, len(groups), 2):
        if groups[i] is not None:
            prefix = groups[i].lower()
            number = groups[i + 1]
            # Handle "Article 5(1)" -> article_5_sub_1
            sub_match = re.match(r'(\d+)\((\d+)\)', number)
            if sub_match:
                return f"{prefix}_{sub_match.group(1)}_sub_{sub_match.group(2)}"
            return f"{prefix}_{number}"
    return None


def extract_articles_from_docling(doc_id: str) -> dict[str, list[int]] | None:
    """Extract article-page mappings from a Docling structure JSON file.

    Args:
        doc_id: The document ID (PDF filename without extension).

    Returns:
        Dict of article_key -> [page_numbers], or None if structure file not found.
    """
    structure_path = os.path.join(DOCLING_DIR, f"{doc_id}_structure.json")
    if not os.path.exists(structure_path):
        return None

    try:
        with open(structure_path) as f:
            structure = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    # Skip case documents (we only want law/regulation articles)
    doc_type = structure.get("type", "")
    if doc_type in ("case", "court_order"):
        return None

    sections = structure.get("sections", [])
    if not sections:
        return None

    articles: dict[str, list[int]] = {}
    for section in sections:
        heading = section.get("heading", "")
        page = section.get("page")
        if not heading or not page:
            continue

        key = _heading_to_key(heading)
        if key is None:
            continue

        if key not in articles:
            articles[key] = []
        if page not in articles[key]:
            articles[key].append(page)

    return articles if articles else None


def classify_document(full_text: str, page_count: int) -> str:
    """Classify document as LAW, CASE, or REGULATION."""
    text_lower = full_text.lower()
    # Court cases have "ORDER" sections, judges, claimant/defendant
    case_signals = ["claimant", "defendant", "respondent", "it is hereby ordered",
                    "order of the court", "judgment", "his honour", "her honour",
                    "chief justice", "deputy chief justice", "j."]
    case_score = sum(1 for s in case_signals if s in text_lower)

    law_signals = ["difc law no.", "law no.", "enacted by", "enactment notice",
                   "preamble", "short title", "interpretation", "commencement"]
    law_score = sum(1 for s in law_signals if s in text_lower)

    regulation_signals = ["rules of the", "regulation no.", "schedule"]
    reg_score = sum(1 for s in regulation_signals if s in text_lower)

    if case_score >= 3:
        return "CASE"
    elif law_score >= 3:
        return "LAW"
    elif reg_score >= 2:
        return "REGULATION"
    elif case_score > law_score:
        return "CASE"
    else:
        return "LAW"


def find_order_pages(doc: pymupdf.Document) -> list[int]:
    """Find pages containing ORDER/disposition section in court cases."""
    order_pages = []
    for page_num in range(len(doc)):
        text = doc[page_num].get_text()
        # Common ORDER section markers
        if any(marker in text for marker in [
            "IT IS HEREBY ORDERED",
            "ORDER OF THE COURT",
            "THE COURT HEREBY ORDERS",
            "The Court orders",
            "DISPOSITION",
        ]):
            order_pages.append(page_num + 1)  # 1-based

    # If no explicit ORDER found, last 2 pages often contain the order
    if not order_pages and len(doc) > 2:
        last_text = doc[-1].get_text().lower()
        if any(w in last_text for w in ["order", "judgment", "dated", "issued"]):
            order_pages = [len(doc)]

    # Detect continuation pages: when numbered items span multiple pages
    # e.g., items 1-2 on header page, items 3-4 on next page
    continuation_pages = []
    for hp in order_pages:
        next_idx = hp  # hp is 1-based, so doc[hp] is the next page (0-indexed)
        while next_idx < len(doc):
            next_text = doc[next_idx].get_text().strip()[:300]
            # Continuation: page starts with a numbered item (e.g., "3." or "4.")
            if re.match(r'^\d+\.', next_text):
                continuation_pages.append(next_idx + 1)  # 1-based
                next_idx += 1
            else:
                break
    order_pages = sorted(set(order_pages + continuation_pages))

    # For cases where ORDER starts on one page but continues, include last page too
    # (DIFC orders often end with "Issued by:" on the last page)
    last_page = len(doc)
    if last_page not in order_pages:
        last_text = doc[-1].get_text()
        if any(m in last_text for m in ["Issued by:", "Date of issue:", "Date of Issue:"]):
            order_pages.append(last_page)

    return sorted(set(order_pages))


def find_date_of_issue_page(doc: pymupdf.Document) -> int:
    """Find the page containing date of issue (usually page 1)."""
    for page_num in range(min(3, len(doc))):
        text = doc[page_num].get_text()
        if any(marker in text for marker in [
            "Date of Issue",
            "Date of Hearing",
            "Date:",
            "Issued:",
        ]):
            return page_num + 1  # 1-based
    return 1  # Default to page 1


def _is_toc_page(text: str) -> bool:
    """Detect if a page is a table of contents (many dotted lines)."""
    dot_lines = len(re.findall(r'\.{5,}', text))
    return dot_lines >= 3


def extract_article_pages(doc: pymupdf.Document) -> dict[str, list[int]]:
    """Extract article/rule/section → page mappings from a document.

    Patterns matched:
    - "Article 28" or "ARTICLE 28" headers (not in TOC pages)
    - "28." at start of line followed by title (DIFC law format)
    - "Rule 28" headers
    - "Section 28" headers
    - "Part 3" headers
    - "Schedule 1" headers
    - "Regulation 3.1" headers (DIFC regulations)
    - "Appendix 1" headers

    Skips TOC/contents pages (detected by many dotted lines).
    For the "N." pattern, requires content text follows (not just a TOC reference).
    """
    articles: dict[str, list[int]] = {}
    # Detect if document is a court case (paragraph numbering ≠ article numbering)
    full_text = ""
    for p in doc:
        full_text += p.get_text()
    is_case = classify_document(full_text, len(doc)) == "CASE"

    for page_num in range(len(doc)):
        text = doc[page_num].get_text()
        is_toc = _is_toc_page(text)

        # Pattern 1: "Article N" or "ARTICLE N" — explicit article keyword
        # Works for both laws AND cases (cases cite articles from other laws)
        if not is_toc:
            for m in re.finditer(r'(?:^|\n)\s*(?:Article|ARTICLE)\s+(\d+[A-Z]?)\b', text):
                key = f"article_{m.group(1)}"
                page = page_num + 1  # 1-based
                if key not in articles:
                    articles[key] = []
                if page not in articles[key]:
                    articles[key].append(page)

        # Pattern 2: "N.\n" or "N. Title" at start of line — DIFC article header
        # ONLY for laws/regulations — court cases use same pattern for paragraph numbers
        # which are NOT articles (e.g., "1. The claimant seeks..." is paragraph 1, not Article 1)
        if not is_toc and not is_case:
            for m in re.finditer(r'(?:^|\n)\s*(\d{1,3})\.\s*\n\s*([A-Z])', text):
                num = m.group(1)
                if int(num) > 300:
                    continue
                key = f"article_{num}"
                page = page_num + 1
                if key not in articles:
                    articles[key] = []
                if page not in articles[key]:
                    articles[key].append(page)
            # Also: "N. Title" on same line
            for m in re.finditer(r'(?:^|\n)\s*(\d{1,3})\.\s+([A-Z][a-z])', text):
                num = m.group(1)
                if int(num) > 300:
                    continue
                # Verify it's not followed by dots (TOC entry)
                after_pos = m.end()
                after_text = text[after_pos:after_pos + 50]
                if '.....' in after_text:
                    continue
                key = f"article_{num}"
                page = page_num + 1
                if key not in articles:
                    articles[key] = []
                if page not in articles[key]:
                    articles[key].append(page)

        # Pattern 3: "Rule N" headers (not on TOC pages)
        if not is_toc:
            for m in re.finditer(r'(?:^|\n)\s*(?:Rule|RULE)\s+(\d+[A-Z]?)\b', text):
                key = f"rule_{m.group(1)}"
                page = page_num + 1
                if key not in articles:
                    articles[key] = []
                if page not in articles[key]:
                    articles[key].append(page)

        # Pattern 4: "Section N" headers
        if not is_toc:
            for m in re.finditer(r'(?:^|\n)\s*(?:Section|SECTION)\s+(\d+[A-Z]?)\b', text):
                key = f"section_{m.group(1)}"
                page = page_num + 1
                if key not in articles:
                    articles[key] = []
                if page not in articles[key]:
                    articles[key].append(page)

        # Pattern 5: "Part N" headers
        if not is_toc:
            for m in re.finditer(r'(?:^|\n)\s*(?:Part|PART)\s+(\d+|[IVXL]+)\b', text):
                key = f"part_{m.group(1)}"
                page = page_num + 1
                if key not in articles:
                    articles[key] = []
                if page not in articles[key]:
                    articles[key].append(page)

        # Pattern 6: "Schedule N" headers
        if not is_toc:
            for m in re.finditer(r'(?:^|\n)\s*(?:Schedule|SCHEDULE)\s+(\d+)\b', text):
                key = f"schedule_{m.group(1)}"
                page = page_num + 1
                if key not in articles:
                    articles[key] = []
                if page not in articles[key]:
                    articles[key].append(page)

        # Pattern 7: "Regulation N" or "Regulation N.N" headers (DIFC regulations)
        if not is_toc:
            for m in re.finditer(r'(?:^|\n)\s*(?:Regulation|REGULATION)\s+(\d+(?:\.\d+)?)\b', text):
                key = f"regulation_{m.group(1)}"
                page = page_num + 1
                if key not in articles:
                    articles[key] = []
                if page not in articles[key]:
                    articles[key].append(page)

        # Pattern 8: "Appendix N" headers
        if not is_toc:
            for m in re.finditer(r'(?:^|\n)\s*(?:Appendix|APPENDIX)\s+(\d+)\b', text):
                key = f"appendix_{m.group(1)}"
                page = page_num + 1
                if key not in articles:
                    articles[key] = []
                if page not in articles[key]:
                    articles[key].append(page)

    return articles


def extract_subsection_pages(doc: pymupdf.Document, articles: dict[str, list[int]]) -> dict[str, list[int]]:
    """Extract subsection-level page mappings for each article.

    For each article, finds the article heading position on its first page, then
    scans text from that heading until the next article heading (or end of scan range)
    for numbered subsection markers like (1), (2), (3) etc.

    Returns a dict of new keys like 'article_28_sub_1': [page] to be merged
    into the articles dict.  Only processes 'article_*' keys (not rule/section/part).
    """
    subsections: dict[str, list[int]] = {}

    # Numbered subsection pattern: standalone "(1)", "(2)" etc. at line start or after whitespace
    sub_num_re = re.compile(r'(?:^|\n)\s*\((\d+)\)\s', re.MULTILINE)

    # Article heading patterns (same ones used in extract_article_pages)
    art_heading_re = re.compile(
        r'(?:^|\n)\s*(?:'
        r'(?:Article|ARTICLE)\s+\d+[A-Z]?\b'
        r'|'
        r'\d{1,3}\.\s*\n\s*[A-Z]'
        r'|'
        r'\d{1,3}\.\s+[A-Z][a-z]'
        r')',
        re.MULTILINE
    )

    # Collect article keys that start with "article_" and have pages
    article_keys = [(k, v) for k, v in articles.items()
                    if k.startswith("article_") and v]

    for art_key, pages in article_keys:
        art_num = art_key.replace("article_", "")

        # The first page where this article heading appears
        heading_page = min(pages)  # 1-based
        max_page = max(pages)  # 1-based
        # Scan through article pages + up to 2 overflow pages
        scan_end = min(max_page + 2, len(doc))  # 0-indexed exclusive
        heading_page_idx = heading_page - 1  # 0-indexed

        # Build a combined text with page boundary markers so we can track pages
        # For each page, find where the article heading starts and where the next
        # article heading begins, and only search that range for subsections
        seen_subs: dict[str, int] = {}  # sub_key -> first page (1-based)

        # Find the article heading position on the heading page
        heading_text = doc[heading_page_idx].get_text()

        # Look for "Article N" or "N." pattern for this specific article
        art_start_pos = None
        # Try "Article N" pattern
        for m in re.finditer(
                r'(?:^|\n)\s*(?:Article|ARTICLE)\s+' + re.escape(art_num) + r'\b',
                heading_text, re.MULTILINE
        ):
            art_start_pos = m.start()
            break
        # Try "N.\n" or "N. Title" pattern
        if art_start_pos is None:
            for m in re.finditer(
                    r'(?:^|\n)\s*' + re.escape(art_num) + r'\.\s',
                    heading_text, re.MULTILINE
            ):
                art_start_pos = m.start()
                break

        if art_start_pos is None:
            # Can't find heading — skip subsection extraction for this article
            continue

        # On the heading page, only search text AFTER the article heading
        search_text = heading_text[art_start_pos:]

        # Check if there's another article heading after this one on the same page
        # (skip the first match which is our own heading)
        next_art_match = None
        for m in art_heading_re.finditer(search_text):
            if m.start() > 0:  # skip the heading itself (at or near position 0)
                next_art_match = m
                break

        if next_art_match:
            # Restrict search to text between this heading and the next
            search_text = search_text[:next_art_match.start()]

        # Find subsections on the heading page
        for m in sub_num_re.finditer(search_text):
            sub_num = m.group(1)
            sub_key = f"{art_key}_sub_{sub_num}"
            if sub_key not in seen_subs:
                seen_subs[sub_key] = heading_page  # 1-based

        # If we stopped at another article heading on the same page, no overflow scan
        if next_art_match and heading_page_idx + 1 >= scan_end:
            pass
        elif not next_art_match:
            # Scan subsequent pages for overflow subsections
            for page_idx in range(heading_page_idx + 1, scan_end):
                page_text = doc[page_idx].get_text()
                page_1based = page_idx + 1

                # Check if there's an article heading on this page — stop before it
                next_heading = art_heading_re.search(page_text)
                if next_heading:
                    # Only search up to the next heading
                    scan_region = page_text[:next_heading.start()]
                else:
                    scan_region = page_text

                for m in sub_num_re.finditer(scan_region):
                    sub_num = m.group(1)
                    sub_key = f"{art_key}_sub_{sub_num}"
                    if sub_key not in seen_subs:
                        seen_subs[sub_key] = page_1based

                # If we hit another article heading, stop scanning further pages
                if next_heading:
                    break

        for sub_key, page in seen_subs.items():
            subsections[sub_key] = [page]

    return subsections


def build_index(merge: bool = True, from_docling: bool = False):
    """Build the complete article-to-page reverse index.

    If merge=True (default), loads the existing index and preserves manual
    corrections: existing article entries are kept, new ones are added.

    If from_docling=True, reads Docling structure JSON files as primary source
    for article-page mappings, falling back to regex extraction. Docling entries
    take precedence over regex-extracted entries for the same key.
    """
    # Load existing index for merge
    existing_index = {}
    if merge and os.path.exists(OUTPUT):
        with open(OUTPUT) as f:
            existing_index = json.load(f)
        print(f"Loaded existing index with {len(existing_index)} entries (merge mode)")

    index = {}
    total_subsections = 0
    articles_with_subs = 0

    pdf_files = sorted(f for f in os.listdir(DOCS_DIR) if f.endswith(".pdf"))
    print(f"Scanning {len(pdf_files)} PDFs...")

    for filename in pdf_files:
        pdf_id = filename.replace(".pdf", "")
        filepath = os.path.join(DOCS_DIR, filename)

        try:
            doc = pymupdf.open(filepath)
        except Exception as e:
            print(f"  ERROR: {pdf_id[:20]}... — {e}")
            continue

        # Get full text for classification
        full_text = ""
        for page in doc:
            full_text += page.get_text()

        doc_type = classify_document(full_text, len(doc))

        # Extract article/rule/section mappings via regex
        article_pages = extract_article_pages(doc)

        # Merge Docling structure if available and requested
        n_docling = 0
        if from_docling:
            docling_articles = extract_articles_from_docling(pdf_id)
            if docling_articles:
                # Docling is primary: Docling entries override regex entries
                merged = dict(article_pages)
                for k, v in docling_articles.items():
                    if k not in article_pages:
                        n_docling += 1
                    merged[k] = v  # Docling wins on conflict
                article_pages = merged

        # Extract subsection-level pages for LAW/REGULATION documents
        n_subs = 0
        if doc_type in ("LAW", "REGULATION"):
            sub_pages = extract_subsection_pages(doc, article_pages)
            if sub_pages:
                article_pages.update(sub_pages)
                n_subs = len(sub_pages)
                total_subsections += n_subs
                # Count how many unique articles got subsection entries
                parent_arts = set(k.rsplit("_sub_", 1)[0] for k in sub_pages)
                articles_with_subs += len(parent_arts)

        # Build document entry
        entry = {
            "type": doc_type,
            "page_count": len(doc),
            "articles": article_pages,
        }

        # For court cases, find ORDER pages and date-of-issue page
        if doc_type == "CASE":
            entry["order_pages"] = find_order_pages(doc)
            entry["date_page"] = find_date_of_issue_page(doc)

        # For laws, find title/preamble page (usually 1-2)
        if doc_type in ("LAW", "REGULATION"):
            entry["preamble_pages"] = [1]  # Always page 1 for DIFC laws

        page_count = len(doc)
        doc.close()

        # Merge with existing entry: preserve manual article corrections
        if merge and pdf_id in existing_index:
            old = existing_index[pdf_id]
            old_articles = old.get("articles", {})
            # Keep all existing article mappings, add new ones from scan
            merged_articles = dict(old_articles)
            new_count = 0
            for k, v in entry["articles"].items():
                if k not in merged_articles:
                    merged_articles[k] = v
                    new_count += 1
            entry["articles"] = merged_articles
            # Preserve other manual fields (order_pages, date_page, preamble_pages)
            for field in ("order_pages", "date_page", "preamble_pages"):
                if field in old and field not in entry:
                    entry[field] = old[field]
            # Keep manual type if it differs
            if old.get("type") and old["type"] != entry["type"]:
                entry["type"] = old["type"]

        index[pdf_id] = entry
        n_articles = len([k for k in article_pages if "_sub_" not in k])
        sub_info = f", {n_subs} subsections" if n_subs > 0 else ""
        docling_info = f", +{n_docling} from Docling" if n_docling > 0 else ""
        order_info = f", ORDER pages: {entry.get('order_pages', [])}" if doc_type == "CASE" else ""
        print(
            f"  {pdf_id[:20]}... [{doc_type}] {page_count}-page, {n_articles} articles{sub_info}{docling_info}{order_info}")

    # Save
    with open(OUTPUT, "w") as f:
        json.dump(index, f, indent=2)

    # Summary stats
    total_articles = sum(len([k for k in e["articles"] if "_sub_" not in k]) for e in index.values())
    total_sub_entries = sum(len([k for k in e["articles"] if "_sub_" in k]) for e in index.values())
    types = {t: sum(1 for e in index.values() if e["type"] == t) for t in ["LAW", "CASE", "REGULATION"]}
    print(
        f"\nIndex built: {len(index)} docs, {total_articles} article mappings, {total_sub_entries} subsection mappings")
    print(f"  {articles_with_subs} articles got subsection entries")
    print(f"Types: {types}")
    print(f"Saved to {OUTPUT}")


if __name__ == "__main__":
    import sys

    merge = "--no-merge" not in sys.argv
    from_docling = "--from-docling" in sys.argv
    build_index(merge=merge, from_docling=from_docling)
