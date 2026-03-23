"""
router.py — Deterministic document routing for DIFC legal RAG pipeline.

Stage 1 of 3: route -> retrieve -> answer.

Given a question and answer_type, determines which documents to search
and extracts metadata shortcuts (case IDs, law names, article numbers).
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"

# Pre-compiled patterns
CASE_ID_PATTERN = re.compile(
    r"(CFI|SCT|CA|ARB|ENF|DEC|TCD|ACT)[\s\-/]*(\d+)\s*(?:/|\-|\s+of\s+)(\d{4})",
    re.IGNORECASE,
)

# Fallback: bare case ID without year, e.g. "DIFC SCT 514", "CFI 043"
BARE_CASE_ID_PATTERN = re.compile(
    r"(?:DIFC\s+)?(SCT|CFI|CA|ARB|ENF|DEC|TCD|ACT)\s+(\d+)",
    re.IGNORECASE,
)

ARTICLE_PATTERN = re.compile(
    r"(?:Article|Art\.?)\s+(\d+)(?:\((\d+)\))?(?:\(([a-z])\))?",
    re.IGNORECASE,
)

SCHEDULE_PATTERN = re.compile(
    r"(?:Schedule)\s+(\d+)",
    re.IGNORECASE,
)

PART_PATTERN = re.compile(
    r"(?:Part)\s+(\d+)",
    re.IGNORECASE,
)

APPENDIX_PATTERN = re.compile(
    r"(?:Appendix|Annex)\s+(\d+)",
    re.IGNORECASE,
)

PAGE_REF_PATTERN = re.compile(
    r"(?:page|pg\.?)\s+(\d+)\s+of\s+(?:the\s+)?(?:document|judgment|order)",
    re.IGNORECASE,
)

# Consultation Paper pattern: "Consultation Paper No. X (of YYYY)"
CONSULTATION_PAPER_PATTERN = re.compile(
    r"[Cc]onsultation\s+[Pp]aper\s+(?:[Nn]o\.?\s*)?(\d+)(?:\s+of\s+(\d{4}))?",
    re.IGNORECASE,
)

# Court Order patterns
COURT_ORDER_PATTERN = re.compile(
    r"(?:DIFC\s+)?Courts?\s+(?:(?:Rules\s+of\s+Court\s+)|(?:Small\s+Claims\s+(?:Tribunal|Leasing\s+Tribunal)\s+))?Order\s+No\.?\s*(\d+)\s+of\s+(\d{4})",
    re.IGNORECASE,
)

DRA_ORDER_PATTERN = re.compile(
    r"DRA\s+Order\s+No\.?\s*(\d+)\s+of\s+(\d{4})",
    re.IGNORECASE,
)

# Topic keywords for consultation paper disambiguation (when year is absent)
CP_TOPIC_KEYWORDS = {
    "strata title": ["strata title"],
    "hotel operating": ["hotel operat"],
    "data protection law": ["data protection law", "new data protection"],
    "data protection regulation": ["data protection regulation", "amended data protection"],
    "intellectual property law": ["intellectual property law", "new intellectual property"],
    "intellectual property regulation": ["intellectual property regulation"],
    "employment law": ["employment law"],
    "employment regulation": ["employment regulation"],
    "companies law": ["companies law", "new companies"],
    "companies regulation": ["companies regulation"],
    "trust law": ["trust law", "new trust"],
    "leasing law": ["leasing law", "new leasing"],
    "leasing regulation": ["leasing regulation"],
    "netting law": ["netting law"],
    "operating regulation": ["operating regulation"],
    "real property": ["real property"],
    "financial collateral": ["financial collateral"],
    "law of security": ["law of security"],
    "security regulation": ["security regulation"],
    "electronic transactions": ["electronic transactions"],
    "prescribed company": ["prescribed company"],
    "venture studio": ["venture studio"],
    "family office": ["family office"],
    "family arrangement": ["family arrangement"],
    "ultimate beneficial ownership": ["ultimate beneficial ownership"],
    "non profit": ["non profit", "non-profit"],
    "variable capital": ["variable capital"],
    "common reporting": ["common reporting"],
    "law amendment": ["law amendment", "amendment law"],
    "insolvency": ["insolvency"],
    "foundations": ["foundations"],
    "difc legislation": ["difc legislation"],
}

# Pattern for "the last page" / "first page" / "second page" references
ORDINAL_PAGE_PATTERN = re.compile(
    r"(?:the\s+)?(first|second|third|last|title|cover)\s+page",
    re.IGNORECASE,
)

# DIFC Law number pattern: "DIFC Law No. X of YYYY" or "DIFC [Name] Law No. X of YYYY"
DIFC_LAW_NO_PATTERN = re.compile(
    r"DIFC\s+(?:\w+\s+)?Law\s+No\.?\s*(\d+)\s+of\s+(\d{4})",
    re.IGNORECASE,
)

# Law name extraction patterns — ordered by specificity (most specific first)
LAW_NAME_PATTERNS = [
    # Full names with "Law on the Application..."
    re.compile(
        r"(?:the\s+)?(?:DIFC\s+)?Law\s+on\s+the\s+Application\s+of\s+Civil\s+and\s+Commercial\s+Laws(?:\s+in\s+the\s+DIFC)?",
        re.IGNORECASE,
    ),
    # "DIFC Law on the Application of Civil and Commercial Laws" without "in the DIFC"
    re.compile(
        r"(?:the\s+)?DIFC\s+Law\s+on\s+the\s+Application\s+of\s+Civil\s+and\s+Commercial\s+Laws",
        re.IGNORECASE,
    ),
    # "Common Reporting Standard Law"
    re.compile(
        r"(?:the\s+)?(?:DIFC\s+)?Common\s+Reporting\s+Standard\s+Law(?:\s+\d{4})?",
        re.IGNORECASE,
    ),
    # "Limited Liability Partnership Law"
    re.compile(
        r"(?:the\s+)?(?:DIFC\s+)?Limited\s+Liability\s+Partnership\s+Law(?:\s+\d{4})?",
        re.IGNORECASE,
    ),
    # "General Partnership Law"
    re.compile(
        r"(?:the\s+)?(?:DIFC\s+)?General\s+Partnership\s+Law(?:\s+\d{4})?",
        re.IGNORECASE,
    ),
    # "Personal Property Law"
    re.compile(
        r"(?:the\s+)?(?:DIFC\s+)?Personal\s+Property\s+Law(?:\s+\d{4})?",
        re.IGNORECASE,
    ),
    # Single-word law names: "Employment Law", "Operating Law", "Foundations Law", "Trust Law"
    re.compile(
        r"(?:the\s+)?(?:DIFC\s+)?(Employment|Operating|Foundations|Trust)\s+Law(?:\s+\d{4})?",
        re.IGNORECASE,
    ),
    # Generic two-word law name: "Real Property Law", "Data Protection Law", etc.
    re.compile(
        r"(?:the\s+)?(?:DIFC\s+)?([A-Z][a-z]+\s+[A-Z][a-z]+)\s+Law(?:\s+\d{4})?",
    ),
    # Generic single-word law name (catch-all, lowest priority): "Insolvency Law", "Contract Law"
    re.compile(
        r"(?:the\s+)?(?:DIFC\s+)?([A-Z][a-z]+)\s+Law(?:\s+\d{4})?",
    ),
]

# Metadata question indicators
METADATA_INDICATORS = {
    "date_of_issue": [
        r"date\s+of\s+issue",
        r"issue\s+date",
        r"issued?\s+(?:earlier|later|first|date)",
        r"earlier\s+(?:date\s+of\s+)?issue",
        r"earlier\s+issue\s+date",
        r"which\s+(?:case|document)\s+(?:has|was)\s+(?:an?\s+)?earlier",
        r"issued\s+(?:earlier|first)",
    ],
    "claim_value": [
        r"claim\s+value",
        r"monetary\s+claim",
        r"higher\s+monetary",
        r"claim\s+(?:value|amount)\s+in\s+AED",
        r"(?:larger|higher|bigger|greater)\s+(?:sum|amount|claim)\s+(?:claimed|value)",
        r"sum\s+claimed\s+by\s+the\s+claimant",
        r"(?:larger|higher|bigger)\s+.*\bclaim",
    ],
    "judge": [
        r"(?:who\s+(?:is|are|was|were)\s+)?(?:the\s+)?judge",
        r"judge\s+(?:who\s+)?presid",
        r"(?:any\s+)?judge\s+(?:in\s+common|common\s+to|involved\s+in\s+both|appeared?\s+in\s+both)",
        r"(?:same|common)\s+judge",
        r"judge\s+(?:who\s+)?(?:participated|presided)\s+(?:over|in)\s+both",
    ],
    "parties": [
        r"(?:who\s+(?:is|are)\s+)?(?:the\s+)?(?:claimant|defendant|parties)",
        r"(?:main\s+)?part(?:y|ies)\s+(?:common|in\s+common|named\s+in\s+both)",
        r"(?:same|common|any)\s+(?:legal\s+)?(?:entities?|individuals?|part(?:y|ies)|company)",
        r"(?:claimant|defendant)s?\s+in\s+(?:the\s+)?case",
        r"listed\s+as\s+(?:the\s+)?(?:claimant|defendant)",
        r"named\s+as\s+a\s+main\s+party",
        r"(?:party|parties)\s+(?:seek|seeking)\s+to\s+enforce",
        r"(?:judgment\s+)?(?:creditor|debtor)",
        r"(?:against\s+which|against\s+whom)\s+.*\benforcement\b",
    ],
    "outcome": [
        r"(?:what\s+was\s+)?(?:the\s+)?(?:result|outcome|ruling|decision)",
        # "rule(?!s\b)": matches "rule"/"ruled" but NOT "rules" (e.g. "DIFC-LCIA rules", "other rules")
        # Without this guard, "other rules" falsely triggers outcome detection → wrong page boost.
        r"(?:court\s+)?(?:decide|rule(?!s\b)|order|grant|dismiss)",
        r"IT\s+IS\s+HEREBY\s+ORDERED",
        r"(?:final\s+)?ruling",
        r"application\s+(?:was\s+)?(?:granted|dismissed|heard)",
        r"costs?\s+(?:were\s+)?awarded",
    ],
}


@dataclass
class RouteResult:
    target_doc_ids: list[str] | None  # None means search full corpus
    metadata_pages: dict[str, int] | None  # doc_id -> page_number for metadata shortcuts
    metadata_answer: Any  # Pre-computed answer from metadata index
    is_cross_case: bool  # True if question references 2+ cases
    case_ids: list[str]  # Extracted case IDs
    law_names: list[str]  # Extracted law names
    article_numbers: list[str]  # Extracted article numbers (e.g., "article_14")
    page_refs: list[int] = field(default_factory=list)  # Explicit page references
    ordinal_pages: list[str] = field(default_factory=list)  # "first", "last", etc.
    metadata_type: str | None = None  # What metadata is being asked about


class Router:
    """Deterministic document router for DIFC legal questions."""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self._case_index: dict = {}
        self._article_index: dict = {}
        self._law_name_index: dict = {}
        self._latest_edition_index: dict = {}
        self._cp_index: dict = {}
        self._court_order_index: dict = {}
        self._appeal_index: dict = {}
        self._cp_topic_map: dict[str, list[str]] = {}  # topic -> [cp_keys]
        self._load_indices()

    def _load_indices(self):
        with open(self.data_dir / "case_metadata_index.json") as f:
            self._case_index = json.load(f)

        with open(self.data_dir / "article_page_index.json") as f:
            self._article_index = json.load(f)

        with open(self.data_dir / "law_name_index.json") as f:
            self._law_name_index = json.load(f)

        with open(self.data_dir / "latest_edition_index.json") as f:
            self._latest_edition_index = json.load(f)

        cp_path = self.data_dir / "consultation_paper_index.json"
        if cp_path.exists():
            with open(cp_path) as f:
                self._cp_index = json.load(f)
            self._build_cp_topic_map()

        co_path = self.data_dir / "court_order_index.json"
        if co_path.exists():
            with open(co_path) as f:
                self._court_order_index = json.load(f)

        appeal_path = self.data_dir / "appeal_index.json"
        if appeal_path.exists():
            with open(appeal_path) as f:
                self._appeal_index = json.load(f)

        logger.info(
            "Router loaded: %d cases, %d docs in article index, %d law name variants, %d CPs, %d court orders, %d appeals",
            len(self._case_index),
            len(self._article_index),
            len([k for k in self._law_name_index if k != "_meta"]),
            len(self._cp_index),
            len(self._court_order_index),
            len(self._appeal_index),
        )

    def _extract_case_ids(self, question: str) -> list[str]:
        """Extract case IDs like CFI 057/2025, SCT 295/2025, etc."""
        case_ids = []
        for match in CASE_ID_PATTERN.finditer(question):
            prefix, number, year = match.group(1), match.group(2), match.group(3)
            full_match = match.group(0)
            # Detect dash-format case IDs (e.g. ENF-022-2023): only dashes, no slash
            is_dash_format = '-' in full_match and '/' not in full_match
            if is_dash_format:
                # Dash-format takes priority: try "ENF-022-2023" key before slash variants
                dash_key = f"{prefix.upper()}-{number.zfill(3)}-{year}"
                if dash_key in self._case_index:
                    case_ids.append(dash_key)
                    continue
            # Normalize: uppercase prefix, pad number with leading zeros as needed
            case_id = f"{prefix.upper()} {number.lstrip('0') or '0'}/{year}"
            # Try exact match first
            if case_id in self._case_index:
                case_ids.append(case_id)
            else:
                # Try zero-padded variants
                for padded in [f"{prefix.upper()} {number.zfill(3)}/{year}",
                               f"{prefix.upper()} {number}/{year}"]:
                    if padded in self._case_index:
                        case_ids.append(padded)
                        break
                else:
                    # Still add it even if not in index (might be in test set)
                    case_ids.append(case_id)

        # Fallback: bare case ID without year (e.g. "DIFC SCT 514", "CFI 043")
        if not case_ids:
            bare_matches = BARE_CASE_ID_PATTERN.findall(question)
            for prefix, number in bare_matches:
                p = prefix.upper()
                # Try multiple number formats: as-is, stripped, zero-padded
                candidates = {f"{p} {number}", f"{p} {number.lstrip('0') or '0'}", f"{p} {number.zfill(3)}"}
                for key in self._case_index:
                    for bare in candidates:
                        if key.startswith(bare + "/") or key == bare:
                            case_ids.append(key)
                            break
                    else:
                        continue
                    break

        return list(dict.fromkeys(case_ids))  # dedupe preserving order

    def _extract_law_names(self, question: str) -> list[str]:
        """Extract law names from the question, returning normalized lookup keys."""
        found = []
        q_lower = question.lower()

        # Build a version with quoted strings removed.
        # Prevents law names inside document titles (e.g. "PROPOSED NEW X LAW") from
        # being used for routing when the question is ABOUT that document, not the law.
        q_no_quotes = re.sub(r'"[^"]*"', ' ', question)
        q_no_quotes = re.sub(r"'[^']*'", ' ', q_no_quotes)
        # Also handle Unicode curly quotes
        q_no_quotes = re.sub(r'[\u201C\u201D][^\u201C\u201D]*[\u201C\u201D]', ' ', q_no_quotes)
        q_no_quotes = re.sub(r'[\u2018\u2019][^\u2018\u2019]*[\u2018\u2019]', ' ', q_no_quotes)
        q_lower_no_quotes = q_no_quotes.lower()

        for pattern in LAW_NAME_PATTERNS:
            for match in pattern.finditer(question):
                raw = match.group(0).strip()
                raw_lower = raw.lower()
                # Skip if this law name only appears inside a quoted string.
                # If it's quoted (e.g. document title), the law name is a reference, not a routing target.
                if raw_lower not in q_lower_no_quotes:
                    continue
                # Normalize: lowercase, strip "the ", "DIFC ", trailing year
                normalized = raw_lower
                normalized = re.sub(r"^the\s+", "", normalized)
                normalized = re.sub(r"^difc\s+", "", normalized)
                normalized = re.sub(r"\s+\d{4}$", "", normalized)
                normalized = normalized.strip()

                if normalized in self._law_name_index:
                    found.append(normalized)
                else:
                    # Try common variants
                    variants = [
                        f"difc {normalized}",
                        raw_lower,
                        f"{normalized} in the difc",
                    ]
                    matched = False
                    for variant in variants:
                        if variant in self._law_name_index:
                            found.append(variant)
                            matched = True
                            break
                    # Last resort: check if "application of civil and commercial laws" is a substring
                    if not matched and "application" in normalized:
                        for key in self._law_name_index:
                            if key != "_meta" and "application" in key:
                                found.append(key)
                                break

        # Fallback: check if any canonical law short names appear outside quotes
        # This catches references like "General Partnership" without "Law" suffix
        if not found:
            canonical_short = {
                "general partnership": "general partnership",
                "limited liability partnership": "limited liability partnership",
                "personal property": "personal property",
                "common reporting standard": "common reporting standard",
                "foundations": "foundations",
                "employment": "employment",
                "operating": "operating",
                "trust": "trust",
                # Specific entity roles that uniquely identify a law
                "registrar": "operating",  # "Registrar" = Registrar of Companies under Operating Law
                # Common abbreviations
                "gp law": "general partnership law",
                "llp law": "limited liability partnership law",
                "crs law": "common reporting standard law",
                "pp law": "personal property law",
            }
            for short_name, lookup_key in canonical_short.items():
                if short_name in q_lower_no_quotes and lookup_key in self._law_name_index:
                    if lookup_key not in found:
                        found.append(lookup_key)

        # Check for standalone law abbreviations as whole words (e.g. "CRS Art 12" or "GP Art 18").
        # Runs unconditionally (not inside `if not found`) to support multi-law questions where
        # one law is already found via patterns but a second law appears only as an abbreviation.
        # Only match abbreviations outside quoted strings.
        abbrev_law_pairs = [
            (r"\bcrs\b", "common reporting standard law"),
            (r"\bgp\b", "general partnership law"),
            (r"\bllp\b", "limited liability partnership law"),
            (r"\bpp\b", "personal property law"),
            (r"\bip\s+law\b", "intellectual property law"),
        ]
        for abbrev_re, law_key in abbrev_law_pairs:
            if re.search(abbrev_re, q_lower_no_quotes) and law_key in self._law_name_index:
                if law_key not in found:
                    found.append(law_key)

        # Also check DIFC Law No. X of YYYY references
        for match in DIFC_LAW_NO_PATTERN.finditer(question):
            law_no = int(match.group(1))
            year = int(match.group(2))
            # Map known DIFC law numbers to names
            difc_law_map = {
                (3, 2018): "foundations law",
                (4, 2004): "general partnership law",
                (1, 2019): "employment law",
                (2, 2019): "employment regulations",  # DIFC Employment Law No. 2 of 2019 = Employment Regulations
                (4, 2018): "trust law",
                (5, 2005): "personal property law",
                (7, 2018): "operating law",
                (5, 2004): "limited liability partnership law",
                (2, 2018): "common reporting standard law",
                (3, 2004): "law on the application of civil and commercial laws in the difc",
                (2, 2022): "operating law",  # Amendment law
                (5, 2018): "companies law",  # DIFC Companies Law No. 5 of 2018
                (4, 2019): "companies regulations",  # DIFC Companies Regulations No. 4 of 2019
            }
            key = (law_no, year)
            if key in difc_law_map:
                name = difc_law_map[key]
                if name not in found:
                    found.append(name)

        # Broad fallback: direct substring match against law_name_index keys.
        # Catches "X Regulations" references that LAW_NAME_PATTERNS miss (they only match "X Law").
        # Always runs: supports multi-law comparison questions where one law is already found
        # via patterns but a second law (e.g. "LEASING" in "...Financial Free Zones or LEASING?")
        # needs to be picked up here. Allows up to 2 fallback matches (for law-vs-law comparisons).
        # Redundancy guard: skip keys that are substrings of (or contain) already-found keys
        # to avoid "leasing" being added when "leasing regulations" is already in found.
        # Uses q_lower_no_quotes to avoid matching law names inside document title quotes.
        _fallback_added = 0
        for key in sorted(
            (k for k in self._law_name_index if k != "_meta"),
            key=len, reverse=True,
        ):
            if key in q_lower_no_quotes and key not in found:
                # Skip if this key is a substring of an already-found key (less specific).
                # E.g., skip "leasing" when "leasing regulations" is already found.
                # Do NOT skip if the new key CONTAINS an already-found key (more specific is fine).
                if any(key in fk for fk in found):
                    continue
                found.append(key)
                _fallback_added += 1
                if _fallback_added >= 2:
                    break  # Cap at 2 to avoid noise from long law-name-index

        # Last-resort: if still empty after all steps (including quote-removal), retry
        # broad fallback using ORIGINAL q_lower (with quoted strings preserved).
        # Handles questions like "What is the official number of the DIFC law titled 'ARBITRATION LAW'?"
        # where the law name is in ALL-CAPS inside quotes and not matched by case-sensitive patterns.
        # Safe because it only fires when found is completely empty (normal extraction failed).
        if not found:
            for key in sorted(
                (k for k in self._law_name_index if k != "_meta"),
                key=len, reverse=True,
            ):
                if key in q_lower and key not in found:
                    found.append(key)
                    break  # One match only (single law, title-based lookup)

        return list(dict.fromkeys(found))  # dedupe preserving order

    def _extract_articles(self, question: str) -> list[str]:
        """Extract article references as normalized keys like 'article_14'."""
        articles = []
        for match in ARTICLE_PATTERN.finditer(question):
            art_num = match.group(1)
            articles.append(f"article_{art_num}")

        for match in SCHEDULE_PATTERN.finditer(question):
            sched_num = match.group(1)
            articles.append(f"schedule_{sched_num}")

        for match in PART_PATTERN.finditer(question):
            part_num = match.group(1)
            articles.append(f"part_{part_num}")

        for match in APPENDIX_PATTERN.finditer(question):
            appendix_num = match.group(1)
            articles.append(f"appendix_{appendix_num}")

        # Catch quoted section references like '"2. Commencement"' or "'1. Citation'"
        for match in re.finditer(r"""['""\u2018\u201C](\d+)\.\s+[A-Z][a-zA-Z]+['""\u2019\u201D]""", question):
            sect_num = match.group(1)
            key = f"article_{sect_num}"
            if key not in articles:
                articles.append(key)

        return list(dict.fromkeys(articles))

    def _extract_page_refs(self, question: str) -> tuple[list[int], list[str]]:
        """Extract explicit page number references and ordinal page references."""
        page_nums = []
        for match in PAGE_REF_PATTERN.finditer(question):
            page_nums.append(int(match.group(1)))

        # Also catch "page N of the document" without "the" etc.
        for match in re.finditer(r"page\s+(\d+)\b", question, re.IGNORECASE):
            num = int(match.group(1))
            if num not in page_nums:
                page_nums.append(num)

        ordinals = []
        for match in ORDINAL_PAGE_PATTERN.finditer(question):
            ordinals.append(match.group(1).lower())

        return page_nums, ordinals

    def _build_cp_topic_map(self):
        """Build reverse mapping: topic -> [cp_keys] for disambiguation."""
        import fitz as _fitz
        docs_dir = self.data_dir / "documents"
        for key, doc_id in self._cp_index.items():
            pdf_path = docs_dir / f"{doc_id}.pdf"
            if not pdf_path.exists():
                continue
            try:
                doc = _fitz.open(str(pdf_path))
                text = doc[0].get_text()
                if len(doc) > 1:
                    text += "\n" + doc[1].get_text()
                doc.close()
                text_lower = text.lower()
                for topic, patterns in CP_TOPIC_KEYWORDS.items():
                    for pat in patterns:
                        if pat in text_lower:
                            self._cp_topic_map.setdefault(topic, []).append(key)
                            break
            except Exception:
                pass

    def _extract_consultation_papers(self, question: str) -> list[str]:
        """Extract consultation paper doc_ids from the question."""
        doc_ids = []
        q_lower = question.lower()
        for match in CONSULTATION_PAPER_PATTERN.finditer(question):
            cp_num = int(match.group(1))
            cp_year = int(match.group(2)) if match.group(2) else None

            if cp_year:
                key = f"cp_{cp_num}_of_{cp_year}"
                if key in self._cp_index:
                    doc_id = self._cp_index[key]
                    if doc_id not in doc_ids:
                        doc_ids.append(doc_id)
            else:
                # Try topic disambiguation
                candidates = [k for k in self._cp_index if k.startswith(f"cp_{cp_num}_of_")]
                if len(candidates) == 1:
                    doc_id = self._cp_index[candidates[0]]
                    if doc_id not in doc_ids:
                        doc_ids.append(doc_id)
                elif candidates:
                    # Try to narrow by topic keywords in the question
                    matched_topics = []
                    for topic, patterns in CP_TOPIC_KEYWORDS.items():
                        for pat in patterns:
                            if pat in q_lower:
                                matched_topics.append(topic)
                                break
                    if matched_topics:
                        narrowed = []
                        for cand in candidates:
                            for topic in matched_topics:
                                if cand in self._cp_topic_map.get(topic, []):
                                    if cand not in narrowed:
                                        narrowed.append(cand)
                        if narrowed:
                            candidates = narrowed
                    # Add all remaining candidates
                    for cand in candidates:
                        doc_id = self._cp_index[cand]
                        if doc_id not in doc_ids:
                            doc_ids.append(doc_id)

        # Fallback: "consultation paper" or "DIFC document" keyword present but no CP number matched.
        # Use topic keywords against the FULL question text (including quoted content)
        # to identify the right CP via the topic map.
        # E.g.: 'the consultation paper "PROPOSED NEW INTELLECTUAL PROPERTY LAW"'
        # E.g.: 'the DIFC document "EMPLOYMENT LAW AMENDMENT LAW & NEW EMPLOYMENT REGULATIONS"'
        if not doc_ids and re.search(
            r'\b(?:consultation\s+paper|difc\s+document)\b', question, re.IGNORECASE
        ):
            matched_topics = []
            for topic, patterns in CP_TOPIC_KEYWORDS.items():
                for pat in patterns:
                    if pat in q_lower:
                        matched_topics.append(topic)
                        break
            if matched_topics:
                # Collect CP candidates that match ANY matched topic
                topic_candidates: dict[str, int] = {}  # cp_key -> match_count
                for topic in matched_topics:
                    for cp_key in self._cp_topic_map.get(topic, []):
                        topic_candidates[cp_key] = topic_candidates.get(cp_key, 0) + 1
                if topic_candidates:
                    # Sort by match count descending; pick the best-matching CP(s)
                    best_count = max(topic_candidates.values())
                    for cp_key, count in sorted(topic_candidates.items(), key=lambda x: -x[1]):
                        if count < best_count:
                            break
                        doc_id = self._cp_index.get(cp_key)
                        if doc_id and doc_id not in doc_ids:
                            doc_ids.append(doc_id)

        return doc_ids

    def _extract_court_orders(self, question: str) -> list[str]:
        """Extract court order doc_ids from the question."""
        doc_ids = []
        for match in COURT_ORDER_PATTERN.finditer(question):
            num = int(match.group(1))
            year = int(match.group(2))
            # Determine order type from context before match
            context = question[max(0, match.start() - 60):match.end()].lower()
            if "rules of court" in context:
                order_type = "rules_of_court"
            elif "small claims" in context:
                order_type = "sct"
            else:
                order_type = "court"

            key = f"{order_type}_order_{num}_of_{year}"
            if key in self._court_order_index:
                doc_id = self._court_order_index[key]
                if doc_id not in doc_ids:
                    doc_ids.append(doc_id)
            else:
                # Try all types as fallback
                for otype in ["court", "sct", "rules_of_court"]:
                    alt_key = f"{otype}_order_{num}_of_{year}"
                    if alt_key in self._court_order_index:
                        doc_id = self._court_order_index[alt_key]
                        if doc_id not in doc_ids:
                            doc_ids.append(doc_id)
                        break

        # DRA Orders
        for match in DRA_ORDER_PATTERN.finditer(question):
            num = int(match.group(1))
            year = int(match.group(2))
            key = f"dra_order_{num}_of_{year}"
            if key in self._court_order_index:
                doc_id = self._court_order_index[key]
                if doc_id not in doc_ids:
                    doc_ids.append(doc_id)

        return doc_ids

    def _detect_metadata_type(self, question: str) -> str | None:
        """Detect what metadata field is being queried."""
        q_lower = question.lower()
        for meta_type, patterns in METADATA_INDICATORS.items():
            for pat in patterns:
                if re.search(pat, q_lower):
                    return meta_type
        return None

    def _get_case_doc_ids(self, case_id: str) -> list[str]:
        """Get all document IDs for a given case ID."""
        if case_id in self._case_index:
            return [doc["doc_id"] for doc in self._case_index[case_id]["docs"]]
        return []

    def _get_law_doc_id(self, law_name: str) -> str | None:
        """Get the document ID for a law name."""
        if law_name in self._law_name_index and law_name != "_meta":
            return self._law_name_index[law_name]
        return None

    def _get_metadata_pages(
        self, case_ids: list[str], metadata_type: str | None
    ) -> dict[str, int] | None:
        """Get metadata page numbers for shortcuts."""
        if not metadata_type or not case_ids:
            return None

        pages = {}
        for case_id in case_ids:
            if case_id not in self._case_index:
                continue
            for doc in self._case_index[case_id]["docs"]:
                doc_id = doc["doc_id"]
                meta = doc.get("metadata", {})

                if metadata_type == "date_of_issue" and isinstance(meta.get("date_of_issue"), dict):
                    page = meta["date_of_issue"].get("page")
                    if page:
                        pages[doc_id] = page
                elif metadata_type == "claim_value":
                    if isinstance(meta.get("claim_value_aed"), dict):
                        page = meta["claim_value_aed"].get("page")
                        if page:
                            pages[doc_id] = page
                    elif isinstance(meta.get("claim_value"), dict):
                        page = meta["claim_value"].get("page")
                        if page:
                            pages[doc_id] = page
                elif metadata_type == "judge" and meta.get("judge"):
                    judges = meta["judge"]
                    if isinstance(judges, list) and judges:
                        pages[doc_id] = judges[0].get("page", 1) if isinstance(judges[0], dict) else 1
                    elif isinstance(judges, dict):
                        pages[doc_id] = judges.get("page", 1)
                elif metadata_type == "parties":
                    # Parties are always on page 1
                    pages[doc_id] = 1
                elif metadata_type == "outcome" and isinstance(meta.get("outcome"), dict):
                    page = meta["outcome"].get("page")
                    if page:
                        pages[doc_id] = page

        return pages if pages else None

    def _get_metadata_answer(
        self, case_ids: list[str], metadata_type: str | None, question: str,
        answer_type: str = "",
    ) -> Any:
        """Try to extract a pre-computed answer from metadata."""
        if not metadata_type or not case_ids:
            return None

        q_lower = question.lower()

        # For claim value comparison questions
        if metadata_type == "claim_value" and len(case_ids) == 2:
            want_max = any(w in q_lower for w in ["higher", "larger", "bigger", "greater", "more"])
            want_min = any(w in q_lower for w in ["lower", "smaller", "less"])
            if want_max or want_min:
                values = {}
                currencies = {}
                for case_id in case_ids:
                    if case_id in self._case_index:
                        for doc in self._case_index[case_id]["docs"]:
                            meta = doc.get("metadata", {})
                            # Check claim_value_aed first (pre-converted to AED)
                            if isinstance(meta.get("claim_value_aed"), dict):
                                val = meta["claim_value_aed"].get("value")
                                if val is not None and val > 0:
                                    if case_id not in values or val > values[case_id]:
                                        values[case_id] = val
                                        currencies[case_id] = "AED"
                            # Fall back to claim_value with currency
                            elif isinstance(meta.get("claim_value"), dict):
                                val = meta["claim_value"].get("value")
                                cur = meta["claim_value"].get("currency", "AED")
                                if val is not None and val > 0:
                                    if case_id not in values or val > values[case_id]:
                                        values[case_id] = val
                                        currencies[case_id] = cur
                # Only compare if both values present and same currency
                if len(values) == 2:
                    curs = list(currencies.values())
                    if curs[0] == curs[1]:
                        if want_max:
                            return max(values, key=values.get)
                        else:
                            return min(values, key=values.get)

        # For date comparison questions
        if metadata_type == "date_of_issue" and len(case_ids) >= 2:
            want_earlier = any(w in q_lower for w in ["earlier", "first"])
            want_later = any(w in q_lower for w in ["later", "last", "most recent", "latest"])
            if want_earlier or want_later:
                dates = {}
                for case_id in case_ids:
                    if case_id in self._case_index:
                        for doc in self._case_index[case_id]["docs"]:
                            meta = doc.get("metadata", {})
                            if isinstance(meta.get("date_of_issue"), dict):
                                date_val = meta["date_of_issue"].get("value")
                                if date_val:
                                    if case_id not in dates or date_val < dates[case_id]:
                                        dates[case_id] = date_val
                # Only compare if ALL case_ids have dates
                if len(dates) == len(case_ids):
                    if want_earlier:
                        return min(dates, key=dates.get)
                    else:
                        return max(dates, key=dates.get)

        # For single-case claim value
        if metadata_type == "claim_value" and len(case_ids) == 1:
            case_id = case_ids[0]
            if case_id in self._case_index:
                for doc in self._case_index[case_id]["docs"]:
                    meta = doc.get("metadata", {})
                    if isinstance(meta.get("claim_value_aed"), dict):
                        return meta["claim_value_aed"].get("value")
                    elif isinstance(meta.get("claim_value"), dict):
                        return meta["claim_value"].get("value")

        # For "who is the defendant/claimant" questions
        # Only applies to name/names answers — free_text questions mentioning "defendants'"
        # should NOT be intercepted here (e.g. "what was the outcome of the Defendants' application")
        if metadata_type == "parties" and len(case_ids) == 1 and answer_type in ("name", "names"):
            case_id = case_ids[0]
            if case_id in self._case_index:
                if "defendant" in q_lower and "claimant" not in q_lower:
                    names = []
                    for doc in self._case_index[case_id]["docs"]:
                        meta = doc.get("metadata", {})
                        if "defendant" in meta:
                            d = meta["defendant"]
                            if isinstance(d, dict):
                                # Single defendant dict: {"name": "X", "page": 1}
                                n = d.get("name") or d.get("names")
                                if isinstance(n, str) and n not in names:
                                    names.append(n)
                                elif isinstance(n, list):
                                    for nm in n:
                                        if isinstance(nm, str) and nm not in names:
                                            names.append(nm)
                            elif isinstance(d, list):
                                # Multiple defendants: [{"name": "X", "page": 1}, ...]
                                for item in d:
                                    if isinstance(item, dict):
                                        nm = item.get("name")
                                        if isinstance(nm, str) and nm not in names:
                                            names.append(nm)
                    if names:
                        return names

        return None

    def _get_article_pages(
        self, doc_id: str, article_keys: list[str]
    ) -> dict[str, int] | None:
        """Get page numbers for specific articles in a document."""
        if doc_id not in self._article_index:
            return None

        doc_articles = self._article_index[doc_id].get("articles", {})
        pages = {}
        for art_key in article_keys:
            if art_key in doc_articles:
                page_list = doc_articles[art_key]
                if page_list:
                    # Use the first (most specific) page for the article
                    pages[doc_id] = page_list[0]
                    break  # One page per doc is enough

        return pages if pages else None

    def route(self, question: str, answer_type: str) -> RouteResult:
        """Route a question to target documents."""
        case_ids = self._extract_case_ids(question)
        law_names = self._extract_law_names(question)
        articles = self._extract_articles(question)
        page_refs, ordinal_pages = self._extract_page_refs(question)
        metadata_type = self._detect_metadata_type(question)

        target_doc_ids = []
        metadata_pages = {}

        # Collect doc IDs from case references
        for case_id in case_ids:
            doc_ids = self._get_case_doc_ids(case_id)
            target_doc_ids.extend(doc_ids)
            # For dash-format case IDs (e.g. ENF-022-2023), also look up the slash-format
            # variant (ENF 022/2023) — some cases have separate index entries for the same case.
            # DIFC case numbers are unique identifiers (type+num+year), so ENF-022-2023 and
            # ENF 022/2023 ALWAYS refer to the same case — just indexed under different format keys.
            # Both entries may have different doc sets (e.g., different orders from same enforcement),
            # and all docs should be included for complete retrieval.
            m = re.match(r'^([A-Z]+)-(\d+)-(\d+)$', case_id)
            if m:
                p, n, y = m.groups()
                for alt in [f"{p} {int(n)}/{y}", f"{p} {n.zfill(3)}/{y}"]:
                    if alt in self._case_index:
                        alt_docs = [doc["doc_id"] for doc in self._case_index[alt]["docs"]]
                        for doc_id in alt_docs:
                            if doc_id not in target_doc_ids:
                                target_doc_ids.append(doc_id)

        # Collect doc IDs from consultation paper references
        cp_doc_ids = self._extract_consultation_papers(question)
        target_doc_ids.extend(cp_doc_ids)

        # Collect doc IDs from court order references
        co_doc_ids = self._extract_court_orders(question)
        target_doc_ids.extend(co_doc_ids)

        # "These Regulations" detection: questions that say "in these Regulations" or
        # "referenced in these Regulations" are context-dependent — the answer is in
        # the currently-discussed regulation doc, NOT in the referenced law.
        # Suppress law-based routing for these questions (let global search find the doc).
        _these_regs_q = bool(re.search(r'\bthese\s+Regulations?\b', question, re.IGNORECASE))

        # Collect doc IDs from law references
        for law_name in law_names:
            doc_id = self._get_law_doc_id(law_name)
            # Skip law routing when the question is about "these Regulations" — the
            # law name is a cross-reference inside the regulations, not the target doc.
            if _these_regs_q and not case_ids and not cp_doc_ids and not co_doc_ids:
                pass  # suppress: will fall through to global search
            elif doc_id and doc_id not in target_doc_ids:
                target_doc_ids.append(doc_id)

            # If we have article references + law doc, get article pages
            if doc_id and articles:
                art_pages = self._get_article_pages(doc_id, articles)
                if art_pages:
                    metadata_pages.update(art_pages)

        # Amendment question detection: "which laws were amended by DIFC Law No. X"
        # These questions need ALL law documents (cover pages list amending legislation).
        # Only trigger when we already have the specific amendment law doc (i.e. the law
        # referenced in the question was found via law_name_index). If target_doc_ids is
        # empty, we haven't found the amendment law, so dumping ALL laws is noise — fall
        # back to global search instead, which has a better chance of finding the right doc.
        q_lower = question.lower()
        if (target_doc_ids and
                (re.search(r"which\b.*\b(?:laws?|legislation)\b.*\bamend", q_lower) or
                 re.search(r"amend(?:ed|ing|ment)\b.*\bwhich\b.*\b(?:laws?|legislation)", q_lower))):
            # Add all law doc IDs from the law_name_index
            for key, doc_id in self._law_name_index.items():
                if key != "_meta" and isinstance(doc_id, str) and doc_id not in target_doc_ids:
                    target_doc_ids.append(doc_id)
                    # Route to cover page (page 1) where amendments are listed
                    metadata_pages[doc_id] = 1

        # Appeal cross-reference: for SCT cases with appeal questions,
        # add the CFI appeal document if it exists in our corpus
        if self._appeal_index and case_ids:
            is_appeal_q = bool(re.search(
                r"appeal(?:ed|ing)?|permission\s+to\s+appeal|PTA\b",
                q_lower,
            ))
            if is_appeal_q:
                for case_id in case_ids:
                    appeal_info = self._appeal_index.get(case_id)
                    if appeal_info and "cfi_doc_id" in appeal_info:
                        cfi_doc_id = appeal_info["cfi_doc_id"]
                        if cfi_doc_id not in target_doc_ids:
                            target_doc_ids.append(cfi_doc_id)
                            logger.info(
                                "Appeal routing: added %s doc for %s -> %s",
                                appeal_info.get("cfi_case", "CFI"),
                                case_id,
                                cfi_doc_id[:16],
                            )

        is_cross_case = len(case_ids) >= 2

        # Get metadata pages for case-based questions.
        # Skip parties page boost for free_text: "parties on page 1" is wrong for questions
        # asking about specific court actions/orders — the content page scores higher without the boost.
        if not (answer_type == "free_text" and metadata_type == "parties"):
            case_meta_pages = self._get_metadata_pages(case_ids, metadata_type)
            if case_meta_pages:
                metadata_pages.update(case_meta_pages)

        # Get pre-computed metadata answer
        metadata_answer = self._get_metadata_answer(case_ids, metadata_type, question, answer_type)

        # "Official number" questions about laws → page 1 (title page has the law number)
        if law_names and re.search(r"official\s+number", q_lower):
            for law_name in law_names:
                doc_id = self._get_law_doc_id(law_name)
                if doc_id:
                    metadata_pages[doc_id] = 1

        # Handle ordinal page references with article index
        if ordinal_pages and target_doc_ids:
            for doc_id in target_doc_ids:
                if doc_id in self._article_index:
                    page_count = self._article_index[doc_id].get("page_count", 0)
                    for ordinal in ordinal_pages:
                        if ordinal == "last" and page_count:
                            metadata_pages[doc_id] = page_count
                        elif ordinal in ("first", "title", "cover"):
                            metadata_pages[doc_id] = 1
                        elif ordinal == "second" and page_count >= 2:
                            metadata_pages[doc_id] = 2
                        elif ordinal == "third" and page_count >= 3:
                            metadata_pages[doc_id] = 3

        # Handle explicit page references
        if page_refs and target_doc_ids:
            for doc_id in target_doc_ids:
                for page_num in page_refs:
                    metadata_pages[doc_id] = page_num

        # Deduplicate target_doc_ids preserving order
        seen = set()
        unique_docs = []
        for doc_id in target_doc_ids:
            if doc_id not in seen:
                seen.add(doc_id)
                unique_docs.append(doc_id)
        target_doc_ids = unique_docs

        result = RouteResult(
            target_doc_ids=target_doc_ids if target_doc_ids else None,
            metadata_pages=metadata_pages if metadata_pages else None,
            metadata_answer=metadata_answer,
            is_cross_case=is_cross_case,
            case_ids=case_ids,
            law_names=law_names,
            article_numbers=articles,
            page_refs=page_refs,
            ordinal_pages=ordinal_pages,
            metadata_type=metadata_type,
        )

        logger.debug(
            "Routed Q to %d docs (cases=%s, laws=%s, articles=%s)",
            len(target_doc_ids) if target_doc_ids else 0,
            case_ids,
            law_names,
            articles,
        )

        return result


# Module-level singleton
_router: Router | None = None


def get_router() -> Router:
    global _router
    if _router is None:
        _router = Router()
    return _router


def route(question: str, answer_type: str) -> RouteResult:
    """Module-level convenience function."""
    return get_router().route(question, answer_type)


# ── Testing ──────────────────────────────────────────────────────────────

def test_routing_coverage():
    """Test router against all 100 public dataset questions."""
    with open(DATA_DIR / "public_dataset.json") as f:
        questions = json.load(f)

    router = Router()
    routed = 0
    fallback = 0
    cross_case = 0
    with_metadata = 0
    with_articles = 0
    with_meta_answer = 0

    print(f"\n{'='*80}")
    print(f"ROUTING COVERAGE TEST — {len(questions)} questions")
    print(f"{'='*80}\n")

    for i, q in enumerate(questions):
        result = router.route(q["question"], q["answer_type"])
        is_routed = result.target_doc_ids is not None

        if is_routed:
            routed += 1
        else:
            fallback += 1

        if result.is_cross_case:
            cross_case += 1
        if result.metadata_pages:
            with_metadata += 1
        if result.article_numbers:
            with_articles += 1
        if result.metadata_answer is not None:
            with_meta_answer += 1

        status = "ROUTED" if is_routed else "FALLBACK"
        doc_count = len(result.target_doc_ids) if result.target_doc_ids else 0
        details = []
        if result.case_ids:
            details.append(f"cases={result.case_ids}")
        if result.law_names:
            details.append(f"laws={result.law_names}")
        if result.article_numbers:
            details.append(f"articles={result.article_numbers}")
        if result.metadata_type:
            details.append(f"meta={result.metadata_type}")
        if result.metadata_answer is not None:
            details.append(f"answer={result.metadata_answer}")
        if result.is_cross_case:
            details.append("CROSS-CASE")

        detail_str = ", ".join(details) if details else ""
        q_short = q["question"][:80] + "..." if len(q["question"]) > 80 else q["question"]
        print(f"  [{status:8s}] {doc_count:2d} docs | {q['answer_type']:10s} | {detail_str}")
        print(f"            Q: {q_short}")

    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"  Total questions:    {len(questions)}")
    print(f"  Routed:             {routed} ({100*routed/len(questions):.1f}%)")
    print(f"  Fallback:           {fallback} ({100*fallback/len(questions):.1f}%)")
    print(f"  Cross-case:         {cross_case}")
    print(f"  With metadata page: {with_metadata}")
    print(f"  With articles:      {with_articles}")
    print(f"  With meta answer:   {with_meta_answer}")
    print(f"{'='*80}\n")

    return routed, fallback


def test_unit():
    """Basic unit tests for router components."""
    router = Router()
    print("\n── Unit Tests ──")
    passed = 0
    failed = 0

    def check(name, condition):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  PASS: {name}")
        else:
            failed += 1
            print(f"  FAIL: {name}")

    # Test case ID extraction
    r = router.route("What is the Date of Issue of the document in case CFI 057/2025?", "date")
    check("Extracts single case ID", r.case_ids == ["CFI 057/2025"])
    check("Maps case to doc IDs", r.target_doc_ids is not None and len(r.target_doc_ids) > 0)
    check("Not cross-case", not r.is_cross_case)
    check("Detects date_of_issue metadata", r.metadata_type == "date_of_issue")

    # Test cross-case
    r = router.route(
        "Do cases SCT 295/2025 and SCT 514/2025 involve any of the same legal entities?",
        "boolean",
    )
    check("Extracts two case IDs", len(r.case_ids) == 2)
    check("Is cross-case", r.is_cross_case)
    check("Detects parties metadata", r.metadata_type == "parties")

    # Test law name extraction
    r = router.route(
        "Under Article 8(1) of the Operating Law 2018, is a person permitted to operate?",
        "boolean",
    )
    check("Extracts Operating Law", "operating law" in r.law_names)
    check("Extracts article_8", "article_8" in r.article_numbers)
    check("Routes to Operating Law doc", r.target_doc_ids is not None)

    # Test Employment Law
    r = router.route(
        "Under Article 14(1) of the Employment Law 2019, how many days?",
        "number",
    )
    check("Extracts Employment Law", "employment law" in r.law_names)
    check("Extracts article_14", "article_14" in r.article_numbers)

    # Test Common Reporting Standard Law
    r = router.route(
        "According to Article 12(4) of the Common Reporting Standard Law 2018, how many years?",
        "number",
    )
    check("Extracts CRS Law", "common reporting standard law" in r.law_names)
    check("Extracts article_12", "article_12" in r.article_numbers)

    # Test multi-law question
    r = router.route(
        "According to Article 12(4) of the Common Reporting Standard Law and Article 18(2)(b) "
        "of the General Partnership Law, what are the retention periods?",
        "free_text",
    )
    check("Extracts two laws", len(r.law_names) == 2)
    check("Has two articles", len(r.article_numbers) == 2)

    # Test Law on Application
    r = router.route(
        "Does the Law on the Application of Civil and Commercial Laws in the DIFC apply?",
        "boolean",
    )
    check("Extracts Application Law", any("application" in n for n in r.law_names))

    # Test DIFC Law No. reference
    r = router.route(
        "Does the DIFC law numbered DIFC Law No. 7 of 2018 deal with insolvency?",
        "boolean",
    )
    check("Maps DIFC Law No. 7/2018 to Operating Law", "operating law" in r.law_names)

    # Test date comparison with metadata answer
    r = router.route(
        "Which case has an earlier Date of Issue: SCT 169/2025 or SCT 295/2025?",
        "name",
    )
    check("Date comparison has metadata_answer", r.metadata_answer is not None)

    # Test claim value comparison
    r = router.route(
        "Identify the case with the higher monetary claim: SCT 169/2025 or SCT 295/2025?",
        "name",
    )
    check("Claim comparison has metadata_answer", r.metadata_answer is not None)

    # Test "last page" reference
    r = router.route(
        "Looking only at the last page of the document in case SCT 514/2025, what was the outcome?",
        "free_text",
    )
    check("Detects last page ordinal", "last" in r.ordinal_pages)
    check("Has metadata pages for last page", r.metadata_pages is not None)

    # Test "page 2" reference
    r = router.route(
        "According to page 2 of the judgment, from which specific claim number did the appeal in CA 009/2024 originate?",
        "name",
    )
    check("Detects explicit page ref", 2 in r.page_refs)

    # Test defendant question
    r = router.route("Who is the defendant in case ARB 034/2025?", "name")
    check("Defendant has parties metadata", r.metadata_type == "parties")

    # Test claimants question
    r = router.route(
        "Who are listed as the claimants in the case documents for SCT 295/2025?",
        "names",
    )
    check("Claimants detection", r.metadata_type == "parties")

    # Test judge common question
    r = router.route(
        "Was the same judge involved in both case CFI 010/2024 and case CFI 016/2025?",
        "boolean",
    )
    check("Judge common detection", r.metadata_type == "judge")
    check("Cross-case for judge Q", r.is_cross_case)

    # Test Foundations Law
    r = router.route(
        "Under the Foundations Law DIFC Law No. 3 of 2018, what is the maximum fine?",
        "free_text",
    )
    check("Extracts Foundations Law", "foundations law" in r.law_names)

    # Test Trust Law
    r = router.route(
        "Under Article 11(5) of the DIFC Trust Law 2018, is a term of the trust valid?",
        "boolean",
    )
    check("Extracts Trust Law", "trust law" in r.law_names)

    # Test title page question for law
    r = router.route(
        "According to the title page of the Common Reporting Standard Law, what is its official DIFC Law number?",
        "number",
    )
    check("Title page routes to CRS Law", r.target_doc_ids is not None)
    check("Title page ordinal detected", "title" in r.ordinal_pages)

    # Test fallback question (no entities)
    r = router.route(
        "What is the minimum period for which accounting records must be preserved?",
        "free_text",
    )
    # This could still match a law; the important thing is it has SOME route or falls back gracefully

    print(f"\n  Results: {passed} passed, {failed} failed out of {passed + failed}\n")
    return failed == 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_unit()
    test_routing_coverage()
