# Answer Quality Optimization Pipeline v2
"""Answer generation for DIFC Legal RAG pipeline (v3).

Single LLM call per question with quality-focused generation.
Pages are pre-selected by the retriever — this module generates and verifies answers.
"""

import json
import logging
import os
import re
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

import anthropic
import pymupdf

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Normalize Unicode to prevent homoglyph mismatches (e.g. Cyrillic lookalikes)."""
    return unicodedata.normalize("NFKC", text)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-6"
MODEL_FREE_TEXT = os.environ.get("MODEL_FREE_TEXT", "claude-opus-4-6")  # Opus for S_asst quality; override via env var
MODEL_DECOMPOSE = "claude-haiku-4-5"  # Haiku for fast question decomposition
MAX_RETRIES = 2
RETRY_DELAYS = [2, 5]  # seconds between retries
MAX_RETRIES_RATE_LIMIT = 3
RETRY_DELAYS_RATE_LIMIT = [10, 30, 60]  # exponential backoff for rate limits

# ---------------------------------------------------------------------------
# Data indices (loaded once at import time)
# ---------------------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

_ARTICLE_INDEX: dict = {}
_article_path = os.path.join(_DATA_DIR, "article_page_index.json")
if os.path.exists(_article_path):
    with open(_article_path) as _f:
        _ARTICLE_INDEX = json.load(_f)

_CASE_META: dict = {}  # case_id -> list of doc entries
_case_meta_path = os.path.join(_DATA_DIR, "case_metadata_index.json")
if os.path.exists(_case_meta_path):
    with open(_case_meta_path) as _f:
        _raw = json.load(_f)
        for case_id, info in _raw.items():
            _CASE_META[case_id.upper()] = info

_APPEAL_INDEX: dict = {}
_appeal_path = os.path.join(_DATA_DIR, "appeal_index.json")
if os.path.exists(_appeal_path):
    with open(_appeal_path) as _f:
        _APPEAL_INDEX = json.load(_f)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class AnswerResult:
    """Result of answer generation."""

    answer: object  # bool, int, float, str, list, or None
    chunk_pages: list[dict] = field(default_factory=list)
    ttft_ms: float = 1.0
    total_time_ms: float = 1.0  # non-zero default: platform penalises total_time_ms=0 (T regression)
    tpot_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    model_name: str = MODEL
    grounding: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Anthropic client (lazy singleton) — supports direct SDK, Vertex AI, and LiteLLM proxy
# ---------------------------------------------------------------------------

_client: anthropic.Anthropic | None = None
_ANTHROPIC_CREDITS_EXHAUSTED: bool = False
_USE_LITELLM: bool = False


def _get_client() -> anthropic.Anthropic | None:
    global _client, _USE_LITELLM
    if _client is None and not _USE_LITELLM:
        backend = os.environ.get("LLM_BACKEND", "litellm").lower()
        if backend == "litellm":
            from arlc.llm import litellm_backend

            if litellm_backend.is_configured():
                _USE_LITELLM = True
                return None
        if backend == "vertex" or (backend == "auto" and os.environ.get("VERTEX_PROJECT_ID")):
            from anthropic import AnthropicVertex

            _client = AnthropicVertex(
                project_id=os.environ["VERTEX_PROJECT_ID"],
                region=os.environ.get("VERTEX_LOCATION", "us-east5"),
            )
        elif backend != "litellm":
            _client = anthropic.Anthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY"),
                timeout=120.0,
            )
    return _client


# ---------------------------------------------------------------------------
# Type-specific system prompts
# ---------------------------------------------------------------------------

_SYSTEM_BOOLEAN = """You are an expert in Dubai International Financial Centre (DIFC) laws and regulations. Answer ONLY based on the provided documents.
Output ONLY: true, false, or null.
- true: the statement is supported by the documents (explicitly stated OR clearly inferable)
- false: the statement is contradicted or clearly inconsistent with the documents
- null: the documents genuinely do not contain enough information
For cross-document comparison questions (e.g. "same judge in both cases"):
- Read each document group separately under === DOCUMENT: ... === headers
- List relevant facts from EACH document before comparing
- Only answer true if the same name/entity appears in BOTH documents
Your first line must be: true, false, or null."""

_SYSTEM_NUMBER = """You are an expert in Dubai International Financial Centre (DIFC) laws and regulations. Extract the exact numeric value from the provided documents.
Output ONLY the number (integer or decimal). No currency symbols, no units, no text, no explanation.
- If the value is expressed as words (e.g., "five"), convert to digits (5)
- If a currency amount, output just the number (e.g., 50000 not AED 50,000)
- If the answer cannot be found, output: null
Your first line must be: the number or null."""

_SYSTEM_NAME = """You are an expert in Dubai International Financial Centre (DIFC) laws and regulations. Extract the exact name requested from the provided documents.
Output ONLY the name exactly as it appears in the document — preserve capitalization and spelling.
- For case numbers: always include the full format with year (e.g., "SCT 295/2025" not "SCT 295")
- If multiple possible answers exist, pick the most specific/direct one
- If the answer cannot be found, output: null
Your first line must be: the name or null."""

_SYSTEM_NAME_DATE_COMPARE = """You are an expert legal document analyst specializing in DIFC cases.

For this date comparison question, follow these steps EXACTLY:

Step 1: For EACH case mentioned in the question, find the "Date of Issue" field. Look for the EXPLICIT label "Date of Issue:" or "Date of issue:" in the document — this is usually on page 1 or 2. Do NOT use dates from referenced prior orders or judgments within the document.

Step 2: Write out each case and its issue date explicitly.

Step 3: Compare the dates chronologically. Remember: July 2025 is EARLIER than January 2026.

CRITICAL: The year in the case NUMBER (e.g., "2023" in ENF 269/2023) is the FILING year, NOT the issue date. You must look for the actual "Date of Issue" field, NOT dates of earlier orders referenced in the text (e.g., "Order dated 19 December 2023" is a REFERENCED order, not this document's issue date).

After your reasoning, on the LAST line, output ONLY the full case name INCLUDING the year (e.g., "ENF 269/2023") — nothing else on that line.
Your last line must be: the full case name with year."""

_SYSTEM_NAME_VALUE_COMPARE = """You are an expert legal document analyst specializing in DIFC cases.

For this value comparison question, follow these steps EXACTLY:

Step 1: Read the question carefully. Determine WHAT monetary value is being compared: claim value, costs, damages awarded, or another amount. Do NOT confuse claim value with costs — they are different.

Step 2: For EACH case mentioned in the question, find the relevant monetary amount. Look for phrases like "claims", "claim value", "amount claimed", "damages of", "debt of", "sum of", "costs", "awarded", "ordered to pay".

Step 3: Write out each case and its amount explicitly.

Step 4: Compare the amounts and identify which is higher/lower as asked.

After your reasoning, on the LAST line, output ONLY the CASE NUMBER with year (e.g., "SCT 169/2025") — nothing else on that line.
CRITICAL: Output a CASE NUMBER (like "SCT 169/2025" or "TCD 001/2023"), NOT a party name. Never output a person's name or company name.
Your last line must be: the case number with year."""

_SYSTEM_NAMES = """You are an expert in Dubai International Financial Centre (DIFC) laws and regulations. Extract the list of names requested from the provided documents.
Output ONLY comma-separated names exactly as they appear in the documents — preserve capitalization.
Example: JOHN SMITH, JANE DOE, ACME CORPORATION
- If the answer cannot be found, output: null
Your first line must be: the comma-separated names or null."""

_SYSTEM_DATE = """You are an expert in Dubai International Financial Centre (DIFC) laws and regulations. Extract the exact date from the provided documents.
Output ONLY in ISO 8601 format: YYYY-MM-DD
- Convert any date format: "15 January 2024" → 2024-01-15; "Jan 15, 2024" → 2024-01-15
- If only year+month available: use first day e.g. 2024-03-01
- If the answer cannot be found, output: null
Your first line must be: the date in YYYY-MM-DD format or null."""

# CoT prompts for free_text (single-call with structured reasoning)
_SYSTEM_FREE_TEXT_LAW = """You are a DIFC legal expert writing precise answers for a professional legal QA evaluation.

Your answer will be scored on 5 BINARY criteria: correctness, completeness, grounding, confidence calibration, and clarity.

FORMAT: First reason in <analysis> tags, then write your final answer in <answer> tags.

<analysis> steps (follow in order):
1. QUESTION PARSE: What exactly is being asked? List each sub-question or aspect.
2. KEY PROVISIONS: For each sub-question, find the relevant article(s). Copy the exact quoted text.
3. CONDITIONS CHECK: Scan source for "unless", "except", "provided that", "subject to", "notwithstanding", "prior approval", "prior consent", "within". List any that apply.
4. GAPS (MANDATORY — never skip): List EVERY aspect of the question that the source does NOT address. Common gaps: specific dates not mentioned, exact monetary amounts absent, procedures not specified, conditions not stated. If you find zero gaps, write "No gaps found." If you skip this step, the answer WILL fail the confidence calibration criterion.
5. DRAFT: Compose the answer following the template below.

ANSWER TEMPLATE (follow in <answer> section):
- First sentence: directly answer the question as a factual statement
- Cite specific articles with verbatim quotes using "states that" phrasing
- Include ALL relevant conditions and exceptions from the source
- If information is absent, state this explicitly ("The Law does not specify...")
- Do NOT add a (Source: ...) citation tag at the end

CALIBRATION EXAMPLES (real gold-standard answers — match this style exactly):

Fully grounded with gap: "According to the Rules of the Dubai International Financial Centre Courts 2014, specifically Rule 9.57, the deadline for filing an acknowledgment of service when a claim form is served out of the DIFC or Dubai is 28 days after the service of the claim form. This same 28-day period also applies to filing or serving an admission in such circumstances. The documents do not specify any specific exceptions to this 28-day period for out-of-jurisdiction service, though general rules allow for time limits to be varied by written agreement of the parties and the Court."

Absence (topic not in document): "The provided 'INTELLECTUAL PROPERTY REGULATIONS' documents do not address or specify tattoo design copyright or body modification studio licensing. The documents outline general procedures for filing and processing intellectual property complaints, conducting inspections, appointing experts, and issuing directions for various types of IP infringements (such as patents, designs, trademarks, copyrights, and trade secrets) within the DIFC, without mentioning specific industries or applications like tattoos or body modification."

ORGANIZER'S CALIBRATION STANDARD:
BAD (overconfident — omits conditions):
"Yes, you can keep ownership of side projects developed on personal time with personal equipment. The policy clearly exempts such work."

GOOD (properly calibrated — states known facts, identifies gaps, acknowledges uncertainty):
"Based on the IP Assignment Agreement, side projects developed on personal time using personal equipment may be exempt from company ownership. However, the policy explicitly requires written approval from the Legal Department prior to commencing work. Since you've already started, this specific situation isn't clearly covered. You should consult the Legal Department to determine whether the exemption can apply after the fact."

RULES:
1. First sentence MUST directly answer the question as a factual statement
2. Address EVERY part of the question — if it asks about two things, cover both
3. Use "states that" when citing legal provisions, with verbatim quotes in double quotes
4. Include the FULL law name (e.g. "Article 28(1) of the General Partnership Law")
5. Attribute EACH factual claim to its source article or page
6. If information is not fully addressed in the source, say "The provisions do not specify..." rather than guessing
7. Do NOT add a (Source: ...) citation tag at the end of the answer
8. 500-650 characters for the <answer> section, no markdown
9. Use definitive language for facts directly stated; qualified language for inferences
10. CRITICAL — CONDITIONS AND EXCEPTIONS: If the source contains conditions ("unless", "except", "provided that", "subject to", "notwithstanding", "upon approval", "prior to", "within", "shall not", "not exceeding"), you MUST mention them. Omitting a stated condition is a critical completeness failure.
11. State what IS established first, then note conditions or limitations.
12. If a provision requires prior approval, registration, written consent, or notice, state this explicitly.
13. CRITICAL: After stating what IS known, explicitly note what the document does NOT specify. Examples: "The Law does not specify the exact timeline for..." / "The provisions are silent on whether..." — Omitting this when information IS absent will fail the confidence calibration criterion.

After your answer in <answer> tags, provide a GROUNDING section listing which pages support each key claim:
GROUNDING:
- "[claim]" → page N
- "[claim]" → page M"""
# Structured reasoning with grounding inspired by guy3 (structure-first methodology)

_SYSTEM_FREE_TEXT_CASE = """You are a DIFC legal expert writing precise answers about DIFC court case outcomes for a professional legal QA evaluation.

Your answer will be scored on 5 BINARY criteria: correctness, completeness, grounding, confidence calibration, and clarity.

FORMAT: First reason in <analysis> tags, then write your final answer in <answer> tags.

<analysis> steps (follow in order):
1. QUESTION PARSE: What is being asked about this case? List each aspect.
2. OUTCOME: What was the court's ruling or order? Find "IT IS HEREBY ORDERED" or equivalent.
3. KEY FACTS: Extract judge name, date, parties, costs, and any conditions on the order.
4. GAPS (MANDATORY — never skip): List EVERY aspect of the question that the source does NOT address. Common gaps: specific dates not mentioned, exact monetary amounts absent, procedures not specified, conditions not stated. If you find zero gaps, write "No gaps found." If you skip this step, the answer WILL fail the confidence calibration criterion.
5. DRAFT: Compose the answer following the rules below.

CALIBRATION EXAMPLE (real gold-standard answer — match this style exactly):
"In Olive v Onyx [2025] DIFC SCT 042, the court held that Article 28 of the DIFC Employment Law provides a clear mechanism for employers and employees upon termination regarding vacation leave. Specifically, Article 28(2) confers a strictly confined right on the employer to deduct an amount from payments due to the employee on the termination date if the employee has taken more vacation leave than accrued. The court emphasized that Article 28 does not create a statutory cause of action or confer a right to sue for recovery of damages for unaccrued leave taken, nor does it create a statutory obligation on the employee to repay wages paid for such days."

ORGANIZER'S CALIBRATION STANDARD:
BAD (overconfident — omits conditions):
"Yes, you can keep ownership of side projects developed on personal time with personal equipment. The policy clearly exempts such work."

GOOD (properly calibrated — states known facts, identifies gaps, acknowledges uncertainty):
"Based on the IP Assignment Agreement, side projects developed on personal time using personal equipment may be exempt from company ownership. However, the policy explicitly requires written approval from the Legal Department prior to commencing work. Since you've already started, this specific situation isn't clearly covered. You should consult the Legal Department to determine whether the exemption can apply after the fact."

RULES:
1. First sentence MUST state the outcome directly (e.g. "The application was dismissed" or "The claim was allowed")
2. ALWAYS include at least one verbatim quote in double quotes from the source — quote "IT IS HEREBY ORDERED THAT" if present, or the key ruling sentence
3. Name the presiding judge/registrar and the date of the order
4. Name ALL parties (Claimant/Defendant or Appellant/Respondent)
5. Include specific costs amounts if mentioned (exact USD/AED figures)
6. Address EVERY aspect the question asks about — if it asks "what happened and why", cover both outcome and reasoning
7. Do NOT add a (Source: ...) citation tag at the end of the answer
8. 500-700 characters for the <answer> section, no markdown
9. State facts definitively when directly quoted from the order; use "the court record indicates" for inferred facts
10. Extract all available information from the provided text
11. CRITICAL — ORDER CONDITIONS: Include ALL conditions attached to court orders (deadlines, reporting requirements, contingencies). If the order says "within 14 days", "subject to assessment", "upon payment of", or "provided that", include it verbatim.
12. CONFIDENCE CALIBRATION: If important details (specific costs amounts, judge name, order date) are genuinely not present in the retrieved source text, explicitly state this (e.g., "No specific costs amounts are mentioned in the order"). This is required — not a flaw.
13. CRITICAL: After stating what IS known, explicitly note what the document does NOT specify. Examples: "No specific costs amount is mentioned in the order." / "The document is silent on whether..." — Omitting this when information IS absent will fail the confidence calibration criterion.

After your answer in <answer> tags, provide a GROUNDING section listing which pages support each key claim:
GROUNDING:
- "[claim]" → page N
- "[claim]" → page M"""

_SYSTEM_FREE_TEXT_TRICK = """You are a DIFC legal expert. The DIFC Courts operate as a civil and commercial jurisdiction under DIFC Law No. 10 of 2004 (the Judicial Authority Law) and DIFC Law No. 12 of 2004 (the Court Law, as amended). There is no criminal jurisdiction, no jury system, no plea bargaining, no Miranda rights, and no parole system.

Write a confident, authoritative answer explaining why the asked concept does not exist in DIFC."""

_CASE_ID_PATTERN = re.compile(r"(?:SCT|CFI|CA|ARB|ENF|DEC|TCD|ACT)\s+\d+/\d{4}", re.IGNORECASE)

_CASE_KEYWORDS = [
    "case cfi",
    "case sct",
    "case arb",
    "case enf",
    "case ca ",
    "case dec",
    "case tcd",
    "arbitration case",
]

_TRICK_KEYWORDS = [
    # Miranda
    "miranda",
    "miranda rights",
    "miranda warning",
    # Jury (bare "jury" omitted — it matches "injury"; handled via regex in finals.py)
    "grand jury",
    "trial by jury",
    "jury trial",
    "jury system",
    "jury decide",
    "did the jury",
    "what did the jury",
    "jury verdict",
    "jury deliberat",
    # Plea
    "plea bargain",
    "plea deal",
    "plea guilty",
    "guilty plea",
    "plea agreement",
    "no contest plea",
    "nolo contendere",
    # Parole / probation (avoid bare "probation" — matches "probation period" in employment law)
    "parole",
    "parole board",
    "probation officer",
    "criminal probation",
    "probation order",
    "on probation",
    # Bail (avoid bare "bail" — matches "bailment" which is a legitimate civil concept)
    "bail bond",
    "post bail",
    "bail hearing",
    "granted bail",
    "denied bail",
    "release on bail",
    "bail amount",
    "bail conditions",
    # Criminal concepts
    "criminal jurisdiction",
    "criminal law",
    "criminal case",
    "criminal charge",
    "criminal prosecution",
    "criminal conviction",
    "criminal sentencing",
    "criminal proceeding",
    "criminal court",
    "criminal trial",
    "criminal record",
    "criminal penalty",
    "criminal sanction",
    # Other
    "habeas corpus",
    "arraignment",
    "indictment",
    "felony",
    "misdemeanor",
    "acquittal",
    "criminal acquittal",
    "criminal appeal",
    "police caution",
    "right to silence",
    "right to remain silent",
    "fifth amendment",
    "fourth amendment",
    "double jeopardy",
    "self-incrimination",
    "prison sentence",
    "jail sentence",
    "imprisonment",
    "incarceration",
    "extradition",
    "death penalty",
    "capital punishment",
    "district attorney",
    "beyond reasonable doubt",
]

# Cyrillic-to-Latin homoglyph mapping for normalization
_CYRILLIC_TO_LATIN: dict[str, str] = {
    "\u0410": "A",
    "\u0412": "B",
    "\u0421": "C",
    "\u0415": "E",
    "\u041d": "H",
    "\u0406": "I",
    "\u041a": "K",
    "\u041c": "M",
    "\u041e": "O",
    "\u0420": "P",
    "\u0422": "T",
    "\u0425": "X",
    "\u0423": "Y",
    "\u0430": "a",
    "\u0435": "e",
    "\u043e": "o",
    "\u0440": "p",
    "\u0441": "c",
    "\u0443": "y",
    "\u0445": "x",
    "\u0456": "i",
}


def check_homoglyphs(text: str) -> str:
    """Replace Cyrillic lookalike characters with their Latin equivalents."""
    return "".join(_CYRILLIC_TO_LATIN.get(c, c) for c in text)


def _decompose_question(question: str) -> str:
    """Break question into sub-questions using Haiku (fast, synchronous).

    Returns a numbered list string of factual elements to address.
    Returns empty string on failure so the caller continues without sub-questions.
    """
    try:
        client = _get_client()
        resp = client.messages.create(
            model=MODEL_DECOMPOSE,
            max_tokens=200,
            temperature=0.0,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "List every distinct factual element or sub-question that must be answered "
                        "to FULLY address this legal question. Be exhaustive.\n\n"
                        f"Question: {question}\n\n"
                        "Output as a numbered list only, no explanations."
                    ),
                }
            ],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        logger.warning(f"[Decompose] Haiku decomp failed: {e}")
        return ""


# ---------------------------------------------------------------------------
# Metadata oracle — instant lookup for known case metadata
# ---------------------------------------------------------------------------


def _judge_as_list(judge_val) -> list[dict]:
    """Normalize judge field: some cases store a single dict, others a list of dicts."""
    if isinstance(judge_val, list):
        return judge_val
    if isinstance(judge_val, dict):
        return [judge_val]
    return []


def _lookup_oracle(question: str, answer_type: str, source_pages: list[dict]) -> AnswerResult | None:
    """Try to answer from pre-computed case metadata.

    Returns AnswerResult if oracle can answer, None otherwise.
    """
    if not _CASE_META:
        return None

    all_case_matches = re.findall(r"(?:SCT|CFI|CA|ARB|ENF|DEC|TCD|ACT)\s+\d+/\d{4}", normalize_text(question), re.I)
    if not all_case_matches:
        return None

    all_case_ids = [re.sub(r"\s+", " ", c).strip().upper() for c in all_case_matches]
    q_lower = question.lower()

    def _find_case_info(case_id: str) -> dict | None:
        """Find the full case info entry (with docs list) for a case ID."""
        info = _CASE_META.get(case_id)
        if info and info.get("docs"):
            return info
        for stored_id, stored_info in _CASE_META.items():
            if case_id in stored_id or stored_id in case_id:
                if stored_info.get("docs"):
                    return stored_info
        return None

    def _find_case_data(case_id: str) -> dict | None:
        """Find metadata for a case ID (first doc)."""
        info = _find_case_info(case_id)
        if info:
            return info["docs"][0].get("metadata", {})
        return None

    def _get_doc_id(case_id: str) -> str:
        """Get primary doc_id for a case."""
        info = _CASE_META.get(case_id)
        if info and info.get("docs"):
            return info["docs"][0].get("doc_id", "")
        for stored_id, stored_info in _CASE_META.items():
            if case_id in stored_id or stored_id in case_id:
                if stored_info.get("docs"):
                    return stored_info["docs"][0].get("doc_id", "")
        return ""

    # Cross-case boolean comparison
    if answer_type == "boolean" and len(all_case_ids) >= 2:
        case1_meta = _find_case_data(all_case_ids[0])
        case2_meta = _find_case_data(all_case_ids[1])
        if case1_meta and case2_meta:
            # Judge comparison
            if any(k in q_lower for k in ["judge", "presided", "presiding"]):

                def _norm_judge(name: str) -> str:
                    name = normalize_text(name)
                    cleaned = re.sub(r"\b(H\.E\.|Justice|Chief|Deputy|Sir|Dr\.?|KC)\b", "", name, flags=re.I)
                    return re.sub(r"\s+", " ", cleaned).strip().lower()

                def _collect_judges(case_id: str) -> set[str]:
                    """Collect judges from ALL docs for a case."""
                    info = _find_case_info(case_id)
                    if not info:
                        return set()
                    judges = set()
                    for doc in info.get("docs", []):
                        meta = doc.get("metadata", {})
                        for j in _judge_as_list(meta.get("judge")):
                            if isinstance(j, dict) and j.get("name"):
                                judges.add(_norm_judge(j["name"]))
                    return judges

                judges1 = _collect_judges(all_case_ids[0])
                judges2 = _collect_judges(all_case_ids[1])
                answer = bool(judges1 & judges2)
                pages = []
                for cid in all_case_ids[:2]:
                    did = _get_doc_id(cid)
                    if did:
                        # Use actual judge page from metadata (judge dict has 'page' field)
                        case_m = _find_case_data(cid) or {}
                        judge_info = case_m.get("judge", {})
                        judge_page = (
                            judge_info[0].get("page", 1)
                            if isinstance(judge_info, list) and judge_info
                            else (judge_info.get("page", 1) if isinstance(judge_info, dict) else 1)
                        )
                        pages.append({"doc_id": did, "page_numbers": [judge_page]})
                logger.info(f"[Oracle] Judge compare: {judges1} vs {judges2} -> {answer}")
                return AnswerResult(answer=answer, chunk_pages=pages)

            # Party comparison
            if any(k in q_lower for k in ["party", "parties", "claimant", "defendant"]):

                def _extract_names_from_party(p) -> list[str]:
                    """Extract party names from any format variant."""
                    names = []
                    if isinstance(p, list):
                        for item in p:
                            if isinstance(item, dict) and item.get("name"):
                                names.append(normalize_text(item["name"]).lower().strip())
                    elif isinstance(p, dict):
                        if p.get("name"):
                            names.append(normalize_text(p["name"]).lower().strip())
                        if p.get("names"):
                            for n in p["names"]:
                                names.append(normalize_text(n).lower().strip())
                    return names

                def _collect_parties(case_id: str) -> set[str]:
                    """Collect parties from ALL docs for a case."""
                    info = _find_case_info(case_id)
                    if not info:
                        return set()
                    parties = set()
                    for doc in info.get("docs", []):
                        meta = doc.get("metadata", {})
                        for key in ["claimant", "defendant"]:
                            parties.update(_extract_names_from_party(meta.get(key)))
                    return parties

                p1, p2 = _collect_parties(all_case_ids[0]), _collect_parties(all_case_ids[1])
                # Exact and fuzzy match
                common = set()
                for a in p1:
                    for b in p2:
                        if a == b or (len(a) > 8 and len(b) > 8 and (a in b or b in a)):
                            common.add(a)
                answer = bool(common)
                pages = []
                for cid in all_case_ids[:2]:
                    did = _get_doc_id(cid)
                    if did:
                        pages.append({"doc_id": did, "page_numbers": [1]})
                logger.info(f"[Oracle] Party compare: {p1} vs {p2} -> {answer}")
                return AnswerResult(answer=answer, chunk_pages=pages)

    # Single-case "judge change" oracle — boolean questions asking if judges changed
    # within a single case (e.g. "Did the panel change in TCD 001/2024?")
    if answer_type == "boolean" and len(all_case_ids) == 1:
        change_keywords = ["change", "changed", "different", "vary", "varied", "alter"]
        judge_keywords = ["judge", "panel", "presiding", "presided"]
        if any(k in q_lower for k in change_keywords) and any(k in q_lower for k in judge_keywords):

            def _norm_judge_name(name: str) -> str:
                name = normalize_text(name)
                cleaned = re.sub(
                    r"\b(H\.E\.|Justice|Chief|Deputy|Sir|Dr\.?|KC|Judicial|Officer)\b", "", name, flags=re.I
                )
                return re.sub(r"\s+", " ", cleaned).strip().lower()

            info = _find_case_info(all_case_ids[0])
            if info:
                # Sort docs chronologically so earliest judge appearances come first
                sorted_docs = sorted(
                    info.get("docs", []),
                    key=lambda d: d.get("metadata", {}).get("date_of_issue", {}).get("value", "9999"),
                )
                # Collect unique judges and their earliest doc
                judge_docs: dict[str, dict] = {}  # norm_name -> earliest doc entry
                for doc in sorted_docs:
                    doc_meta = doc.get("metadata", {})
                    for j in _judge_as_list(doc_meta.get("judge")):
                        if isinstance(j, dict) and j.get("name"):
                            norm = _norm_judge_name(j["name"])
                            if norm and norm not in judge_docs:
                                judge_docs[norm] = doc
                if len(judge_docs) >= 2:
                    # Judges changed — cite one doc per unique judge
                    pages = []
                    for norm_name, doc_entry in judge_docs.items():
                        did = doc_entry.get("doc_id", "")
                        if did:
                            pages.append({"doc_id": did, "page_numbers": [1]})
                    logger.info(f"[Oracle] Judge change in {all_case_ids[0]}: {list(judge_docs.keys())} -> True")
                    return AnswerResult(answer=True, chunk_pages=pages)

    # Cross-case name comparison (answer is a case ID, not a person name)
    # Handles: "Which case was issued earlier?", "Which had higher claim?", "Which had more defendants?"
    if answer_type == "name" and len(all_case_ids) >= 2:
        case1_meta = _find_case_data(all_case_ids[0])
        case2_meta = _find_case_data(all_case_ids[1])
        if case1_meta and case2_meta:
            # Date comparison: "earlier", "later", "more recent", "first"
            if any(k in q_lower for k in ["earlier", "later", "more recent", "first issued", "before", "after"]):
                doi1 = case1_meta.get("date_of_issue", {})
                doi2 = case2_meta.get("date_of_issue", {})
                if isinstance(doi1, dict) and isinstance(doi2, dict) and doi1.get("value") and doi2.get("value"):
                    d1, d2 = doi1["value"], doi2["value"]
                    if any(k in q_lower for k in ["earlier", "first", "before"]):
                        winner = all_case_ids[0] if d1 < d2 else all_case_ids[1]
                    else:
                        winner = all_case_ids[0] if d1 > d2 else all_case_ids[1]
                    pages = []
                    for cid in all_case_ids[:2]:
                        did = _get_doc_id(cid)
                        if did:
                            pages.append({"doc_id": did, "page_numbers": [1]})
                    logger.info(
                        f"[Oracle] Date comparison: {all_case_ids[0]}={d1} vs {all_case_ids[1]}={d2} -> {winner}"
                    )
                    return AnswerResult(answer=winner, chunk_pages=pages)

            # Claim amount comparison: "higher claim", "larger amount", "more claimed"
            if any(
                k in q_lower
                for k in [
                    "higher claim",
                    "larger claim",
                    "more claimed",
                    "greater amount",
                    "higher amount",
                    "larger amount",
                    "bigger",
                ]
            ):

                def _get_claim(m):
                    for key in ["claim_value_aed", "claim_value"]:
                        cv = m.get(key, {})
                        if isinstance(cv, dict) and cv.get("value"):
                            return cv["value"]
                    return None

                v1, v2 = _get_claim(case1_meta), _get_claim(case2_meta)
                if v1 is not None and v2 is not None:
                    winner = all_case_ids[0] if float(v1) > float(v2) else all_case_ids[1]
                    pages = []
                    for cid in all_case_ids[:2]:
                        did = _get_doc_id(cid)
                        if did:
                            pages.append({"doc_id": did, "page_numbers": [1]})
                    logger.info(
                        f"[Oracle] Claim comparison: {all_case_ids[0]}={v1} vs {all_case_ids[1]}={v2} -> {winner}"
                    )
                    return AnswerResult(answer=winner, chunk_pages=pages)

            # Party count comparison: "more defendants", "more claimants"
            if any(k in q_lower for k in ["more defendant", "more claimant", "fewer defendant", "fewer claimant"]):
                role = "defendant" if "defendant" in q_lower else "claimant"

                def _count_parties(m):
                    p = m.get(role, [])
                    if isinstance(p, list):
                        return len(p)
                    elif isinstance(p, dict) and p.get("names"):
                        return len(p["names"])
                    return 1 if p else 0

                c1, c2 = _count_parties(case1_meta), _count_parties(case2_meta)
                if "fewer" in q_lower:
                    winner = all_case_ids[0] if c1 < c2 else all_case_ids[1]
                else:
                    winner = all_case_ids[0] if c1 > c2 else all_case_ids[1]
                pages = []
                for cid in all_case_ids[:2]:
                    did = _get_doc_id(cid)
                    if did:
                        pages.append({"doc_id": did, "page_numbers": [1]})
                logger.info(
                    f"[Oracle] Party count comparison: {all_case_ids[0]}={c1} vs {all_case_ids[1]}={c2} -> {winner}"
                )
                return AnswerResult(answer=winner, chunk_pages=pages)

    # Single-case lookups
    case_id = all_case_ids[0]
    meta = _find_case_data(case_id)
    if not meta:
        return None
    doc_id = _get_doc_id(case_id)

    # Appeal oracle: for boolean "was case X appealed to CFI?" questions,
    # check appeal_index. If pta_filed is true, the case WAS appealed (regardless of outcome).
    # The document itself is a CFI appeal ruling when PTA was filed.
    if answer_type == "boolean" and _APPEAL_INDEX:
        appeal_q_match = bool(
            re.search(
                r"appeal(?:ed|ing)?\s+to\s+(?:the\s+)?(?:CFI|court\s+of\s+first\s+instance)",
                q_lower,
            )
        )
        if appeal_q_match:
            appeal_info = _APPEAL_INDEX.get(case_id)
            if appeal_info and appeal_info.get("pta_filed"):
                logger.info(f"[Oracle] Appeal PTA filed for {case_id}: True")
                return AnswerResult(
                    answer=True,
                    chunk_pages=[{"doc_id": doc_id, "page_numbers": [1]}] if doc_id else [],
                )

    # Date of issue — only trigger when question actually asks about the document's issue date
    date_keywords = [
        "date of issue",
        "issued date",
        "issue date",
        "date of order",
        "date of judgment",
        "date of the order",
        "when was the order",
        "when was the judgment",
    ]
    if answer_type == "date" and any(k in q_lower for k in date_keywords):
        doi = meta.get("date_of_issue", {})
        if isinstance(doi, dict) and doi.get("value"):
            page = doi.get("page", 1)
            logger.info(f"[Oracle] Date: {doi['value']}")
            return AnswerResult(
                answer=doi["value"],
                chunk_pages=[{"doc_id": doc_id, "page_numbers": [page]}] if doc_id else [],
            )

    # Judge name — skip oracle if asking about original/first instance judge (oracle may have appeal judge)
    appeal_keywords = ["original judgment", "original judge", "first instance", "trial judge", "lower court"]
    if (
        answer_type in ("name", "names")
        and any(k in q_lower for k in ["judge", "presided", "presiding"])
        and not any(k in q_lower for k in appeal_keywords)
    ):
        judges = _judge_as_list(meta.get("judge"))
        if judges:
            if answer_type == "name":
                answer = judges[0]["name"]
            else:
                answer = [j["name"] for j in judges]
            page = judges[0].get("page", 1)
            logger.info(f"[Oracle] Judge: {answer}")
            return AnswerResult(
                answer=answer,
                chunk_pages=[{"doc_id": doc_id, "page_numbers": [page]}] if doc_id else [],
            )

    # Claimant/defendant
    if answer_type in ("name", "names"):

        def _extract_party_answer(party_val, answer_type: str) -> tuple[object, int] | None:
            """Extract answer and page from any party format. Returns (answer, page) or None."""
            if isinstance(party_val, list):
                names = [item["name"] for item in party_val if isinstance(item, dict) and item.get("name")]
                if names:
                    page = party_val[0].get("page", 1) if isinstance(party_val[0], dict) else 1
                    return (names[0] if answer_type == "name" else names, page)
            elif isinstance(party_val, dict):
                if party_val.get("name"):
                    page = party_val.get("page", 1)
                    return (party_val["name"] if answer_type == "name" else [party_val["name"]], page)
                if party_val.get("names"):
                    page = party_val.get("page", 1)
                    names = party_val["names"]
                    return (names[0] if answer_type == "name" else names, page)
            return None

        # Skip party oracle if asking about counsel/lawyer/representative (avoid returning party name)
        # Also skip for multi-case comparison questions ("which case had the larger sum claimed by the
        # claimant" — the answer is a case ID, not a party name; using all_case_ids[0]'s claimant
        # would be wrong). Single-case guard: only trigger when exactly 1 case ID is in the question.
        counsel_keywords = ["counsel", "lawyer", "attorney", "representative", "solicitor", "barrister", "advocate"]
        comparison_keywords = [
            "which case",
            "between",
            "larger",
            "smaller",
            "higher",
            "lower",
            "more than",
            "less than",
            "compared",
            "comparison",
        ]
        _is_single_case = len(all_case_ids) == 1
        _is_comparison = any(k in q_lower for k in comparison_keywords)
        if (
            _is_single_case
            and not _is_comparison
            and any(k in q_lower for k in ["claimant", "plaintiff", "applicant"])
            and not any(k in q_lower for k in counsel_keywords)
        ):
            result = _extract_party_answer(meta.get("claimant"), answer_type)
            if result:
                answer, page = result
                logger.info(f"[Oracle] Claimant: {answer}")
                return AnswerResult(
                    answer=answer,
                    chunk_pages=[{"doc_id": doc_id, "page_numbers": [page]}] if doc_id else [],
                )
        if (
            _is_single_case
            and not _is_comparison
            and any(k in q_lower for k in ["defendant", "respondent"])
            and not any(k in q_lower for k in counsel_keywords)
        ):
            result = _extract_party_answer(meta.get("defendant"), answer_type)
            if result:
                answer, page = result
                logger.info(f"[Oracle] Defendant: {answer}")
                return AnswerResult(
                    answer=answer,
                    chunk_pages=[{"doc_id": doc_id, "page_numbers": [page]}] if doc_id else [],
                )

    # Claim value
    if answer_type == "number" and any(k in q_lower for k in ["claim value", "amount claimed", "claimed"]):
        cv = meta.get("claim_value_aed", {})
        if isinstance(cv, dict) and cv.get("value"):
            page = cv.get("page", 1)
            logger.info(f"[Oracle] Claim value: {cv['value']}")
            return AnswerResult(
                answer=cv["value"],
                chunk_pages=[{"doc_id": doc_id, "page_numbers": [page]}] if doc_id else [],
            )

    # Enforcement amount — "sum in AED subject of enforcement proceedings"
    # For ENF cases, the claim_value in the main enforcement doc (first doc) has the amount.
    # This prevents the retriever picking a costs assessment doc instead.
    if answer_type == "number" and re.search(r"(?:sum|amount).*enforcement", q_lower):
        cv = meta.get("claim_value")
        if isinstance(cv, dict) and cv.get("value"):
            page = cv.get("page", 1)
            logger.info(f"[Oracle] Enforcement amount: {cv['value']}")
            return AnswerResult(
                answer=cv["value"],
                chunk_pages=[{"doc_id": doc_id, "page_numbers": [page]}] if doc_id else [],
            )

    # Count unique claimants / defendants
    if answer_type == "number":
        _claimant_kw = [
            "unique claimants",
            "distinct claimants",
            "claimants brought",
            "parties initiated",
            "claimants in case",
        ]
        _defendant_kw = [
            "unique defendants",
            "distinct defendants",
            "defendants named",
            "parties defending",
            "parties were defending",
            "defendants in case",
        ]

        def _count_unique_party_names(cid: str, role: str) -> int | None:
            """Count unique party names (across all docs) for a given role."""
            info = _find_case_info(cid)
            if not info:
                return None
            names: set[str] = set()
            for doc in info.get("docs", []):
                party = doc.get("metadata", {}).get(role)
                if isinstance(party, list):
                    for item in party:
                        if isinstance(item, dict) and item.get("name"):
                            names.add(normalize_text(item["name"]).lower().strip())
                elif isinstance(party, dict):
                    if party.get("name"):
                        names.add(normalize_text(party["name"]).lower().strip())
                    for n in party.get("names") or []:
                        names.add(normalize_text(n).lower().strip())
            return len(names) if names else None

        if any(k in q_lower for k in _claimant_kw):
            count = _count_unique_party_names(case_id, "claimant")
            if count is not None:
                logger.info(f"[Oracle] Unique claimants: {count}")
                return AnswerResult(
                    answer=count,
                    chunk_pages=[{"doc_id": doc_id, "page_numbers": [1]}] if doc_id else [],
                )
        if any(k in q_lower for k in _defendant_kw):
            count = _count_unique_party_names(case_id, "defendant")
            if count is not None:
                logger.info(f"[Oracle] Unique defendants: {count}")
                return AnswerResult(
                    answer=count,
                    chunk_pages=[{"doc_id": doc_id, "page_numbers": [1]}] if doc_id else [],
                )

    return None


# ---------------------------------------------------------------------------
# Prompt routing
# ---------------------------------------------------------------------------


def _is_case_question(question: str) -> bool:
    q_lower = question.lower()
    if any(kw in q_lower for kw in _CASE_KEYWORDS):
        return True
    # Also detect case IDs directly (e.g., "In SCT 169/2025, ..." or "ENF 022/2023")
    if _CASE_ID_PATTERN.search(question):
        return True
    return False


def _is_trick_question(question: str) -> bool:
    q_lower = question.lower()
    # Level 1: Exact keyword match — ALWAYS triggers, even with case ID.
    # These are inherently criminal/non-DIFC concepts (miranda, jury, plea, parole).
    if any(kw in q_lower for kw in _TRICK_KEYWORDS):
        return True
    # Skip Level 2+ if question references specific case IDs — those are real case questions
    if _CASE_ID_PATTERN.search(question):
        return False
    return False


def _is_date_compare(question: str) -> bool:
    q_lower = question.lower()
    has_multiple_cases = len(_CASE_ID_PATTERN.findall(question)) >= 2
    return has_multiple_cases and any(
        k in q_lower for k in ["earlier", "later", "before", "after", "first", "more recent"]
    )


def _is_value_compare(question: str) -> bool:
    q_lower = question.lower()
    has_multiple_cases = len(_CASE_ID_PATTERN.findall(question)) >= 2
    return has_multiple_cases and any(
        k in q_lower for k in ["higher", "lower", "larger", "smaller", "greater", "more", "less"]
    )


def _apply_web_mode(prompt: str) -> str:
    """Replace competition formatting rules with web-friendly markdown + source links.

    NOTE: Only affects _SYSTEM_FREE_TEXT_LAW — the "500-650 characters" target string
    and the calibration example only exist in that prompt. Case and trick prompts pass
    through unchanged (case has "500-700", trick has no formatting rules).
    """
    # Replace rule 8: competition char limit -> markdown formatting instructions
    prompt = prompt.replace(
        "8. 500-650 characters for the <answer> section, no markdown",
        "8. FORMAT the <answer> section with markdown:\n"
        "   - **Bold** every article/section number and law name (MANDATORY)\n"
        "   - Bullet points (- ) for multiple conditions/exceptions\n"
        "   - > blockquotes for verbatim legal quotes\n"
        "   - No character limit — be thorough\n"
        "   - After each citation, add [[source:DOC_ID:PAGE]] with the actual doc_id and page from the source\n"
        "   EXAMPLE <answer>:\n"
        "   **Article 9(1)** of **DIFC Law No. 5 of 2005** [[source:abc123:12]] states that:\n"
        '   > "Notwithstanding Article 38, where a cause of action arises as a result of fraud, there is no time limit."\n'
        "   Key conditions:\n"
        "   - The limitation period is **six years** for contract claims\n"
        "   - For tort claims, the period is **three years**",
    )
    # Replace plain-text calibration example with markdown version
    prompt = prompt.replace(
        'Fully grounded with gap: "According to the Rules of the Dubai International Financial Centre Courts 2014, specifically Rule 9.57, the deadline',
        'Fully grounded with gap: "According to **Rule 9.57** of the **DIFC Courts Rules 2014** [[source:RULES2014:15]], the deadline',
    )
    return prompt


def _get_system_prompt(question: str, answer_type: str, web_mode: bool = False) -> str:
    """Select the best system prompt for the question type.

    web_mode only affects free_text prompts (markdown formatting, no char limit).
    Non-free_text types (boolean/number/name/names/date) are unaffected.
    """
    if answer_type == "boolean":
        return _SYSTEM_BOOLEAN
    if answer_type == "number":
        return _SYSTEM_NUMBER
    if answer_type == "name":
        if _is_date_compare(question):
            return _SYSTEM_NAME_DATE_COMPARE
        if _is_value_compare(question):
            return _SYSTEM_NAME_VALUE_COMPARE
        return _SYSTEM_NAME
    if answer_type == "names":
        return _SYSTEM_NAMES
    if answer_type == "date":
        return _SYSTEM_DATE

    # free_text: choose between law, case, and trick prompts
    if _is_trick_question(question):
        base = _SYSTEM_FREE_TEXT_TRICK
    elif _is_case_question(question):
        base = _SYSTEM_FREE_TEXT_CASE
    else:
        base = _SYSTEM_FREE_TEXT_LAW

    return _apply_web_mode(base) if web_mode else base


def _get_max_tokens(answer_type: str) -> int:
    if answer_type == "free_text":
        return 1500  # CoT needs room for <analysis> + <answer> on mega-context law questions
    if answer_type == "name":  # comparison prompts use chain-of-thought
        return 280
    return 80  # +16 tokens for PAGES_USED: line


# ---------------------------------------------------------------------------
# Context building from pre-selected source pages
# ---------------------------------------------------------------------------


def _build_context(source_pages: list[dict], question: str) -> str:
    """Build context string from pre-selected source pages.

    Groups pages by document with clear headers for cross-document comparison.
    """
    if not source_pages:
        return ""

    # Detect multi-doc for grouped format
    unique_docs = {p["doc_id"] for p in source_pages}
    multi_doc = len(unique_docs) > 1

    parts = []
    source_num = 1

    if multi_doc:
        # Group by document for cross-case comparison clarity
        by_doc: dict[str, list[dict]] = {}
        for page in source_pages:
            did = page["doc_id"]
            if did not in by_doc:
                by_doc[did] = []
            by_doc[did].append(page)

        for doc_id, doc_pages in by_doc.items():
            # Get document label from article index
            doc_info = _ARTICLE_INDEX.get(doc_id, {})
            doc_type = doc_info.get("type", "UNKNOWN")
            parts.append(f"=== DOCUMENT: {doc_id[:20]}... ({doc_type}) ===")

            for page in doc_pages:
                pn = page["page_number"]
                text = page.get("text", "")
                header = f"[SOURCE {source_num} | Page: {pn}]"
                parts.append(f"{header}\n{text}")
                source_num += 1
    else:
        for page in source_pages:
            pn = page["page_number"]
            text = page.get("text", "")
            header = f"[SOURCE {source_num} | Page: {pn}]"
            parts.append(f"{header}\n{text}")
            source_num += 1

    return "\n\n---\n\n".join(parts)


def _build_user_message(question: str, context: str, answer_type: str, sub_questions: str = "") -> str:
    """Build the user message with context and question."""
    if answer_type == "free_text":
        if _is_trick_question(question):
            return (
                f"Question: {question}\n\n"
                "This question asks about a concept that does not exist in DIFC law. "
                "Write 400-600 characters:\n"
                "1. State clearly in the first sentence that this concept does not exist in DIFC\n"
                "2. Name the specific DIFC law that establishes the court's civil/commercial jurisdiction\n"
                "3. Briefly explain what DIFC provides instead\n"
                "No markdown."
            )

        # Sub-questions section (from Haiku decomposition)
        sub_q_section = ""
        if sub_questions:
            sub_q_section = f"\nSub-questions to address (ALL must be covered):\n{sub_questions}\n"

        if _is_case_question(question):
            # Bug 1: Inject case metadata (judge, parties, date) from index so model
            # has correct context even when only later pages are retrieved.
            case_ids_in_q = re.findall(r"(?:SCT|CFI|CA|ARB|ENF|DEC|TCD|ACT)\s+\d+/\d{4}", question, re.I)
            metadata_block = ""
            for cid in case_ids_in_q:
                cid_upper = re.sub(r"\s+", " ", cid).strip().upper()
                info = _CASE_META.get(cid_upper, {})
                if info and info.get("docs"):
                    m = info["docs"][0].get("metadata", {})
                    ctx_parts = []
                    judge = m.get("judge", {})
                    if isinstance(judge, list):
                        names = [j.get("name", "") for j in judge if isinstance(j, dict) and j.get("name")]
                        if names:
                            ctx_parts.append(f"Presiding Judge(s): {', '.join(names)}")
                    elif isinstance(judge, dict) and judge.get("name"):
                        ctx_parts.append(f"Presiding Judge: {judge['name']}")
                    claimant = m.get("claimant", {})
                    if isinstance(claimant, dict) and claimant.get("name"):
                        ctx_parts.append(f"Claimant: {claimant['name']}")
                    defendant = m.get("defendant", {})
                    if isinstance(defendant, dict):
                        if defendant.get("name"):
                            ctx_parts.append(f"Defendant: {defendant['name']}")
                        elif defendant.get("names"):
                            ctx_parts.append(f"Defendants: {', '.join(defendant['names'])}")
                    doi = m.get("date_of_issue", {})
                    if isinstance(doi, dict) and doi.get("value"):
                        ctx_parts.append(f"Date of Issue: {doi['value']}")
                    if ctx_parts:
                        metadata_block += f"CASE METADATA ({cid_upper}):\n" + "\n".join(ctx_parts) + "\n\n"
            return (
                f"Question: {question}\n"
                f"{sub_q_section}\n"
                f"{metadata_block}"
                f"Source text (court document):\n{context}\n\n"
                "Write ONE precise answer about this case outcome. Include:\n"
                "- Direct outcome in first sentence\n"
                "- MANDATORY: at least one verbatim quote in double quotes (from IT IS HEREBY ORDERED THAT, or ruling, or key sentence)\n"
                "- Presiding judge/registrar name and order date\n"
                "- All parties (Claimant/Defendant or Appellant/Respondent)\n"
                "- Exact costs amounts if mentioned (USD/AED figures)\n"
                "- Do NOT add a source citation tag at the end\n"
                "- If a key detail (costs, judge name, date) is genuinely absent from the source, state this explicitly for confidence calibration\n"
                "STRICT 500-650 characters for the <answer> section. Start with the direct outcome.\n\n"
                "After your answer, on a NEW line output ONLY: "
                "PAGES_USED: [comma-separated page numbers from the [SOURCE | Page: N] headers that directly support your answer]"
            )
        # Law question — pre-extract condition markers from source
        _condition_markers = [
            "unless",
            "except",
            "provided that",
            "subject to",
            "notwithstanding",
            "upon",
            "prior to",
            "within",
            "not exceeding",
            "shall not",
            "written approval",
            "written consent",
            "prior written",
            "provided however",
        ]
        condition_sentences = []
        seen_cond = set()
        for sent in re.split(r"(?<=[.;])\s+", context):
            sent_lower = sent.lower()
            for marker in _condition_markers:
                if marker in sent_lower:
                    key = sent[:80]
                    if key not in seen_cond and len(sent.strip()) > 15:
                        condition_sentences.append(sent.strip())
                        seen_cond.add(key)
                    break

        cond_note = ""
        if condition_sentences:
            cond_note = "\n\nIMPORTANT CONDITIONS IN SOURCE (must address all that are relevant):\n"
            for c in condition_sentences[:3]:
                cond_note += f"- {c[:200]}\n"

        return (
            f"Question: {question}\n"
            f"{sub_q_section}\n"
            f"Source text:\n{context}\n\n"
            "Write ONE precise answer following the TEMPLATE exactly. "
            "Use 'states:' or 'states that' to introduce verbatim quotes in SINGLE quotes. "
            "Do NOT add a source citation tag at the end. "
            f"500-650 characters for the <answer> section. Start with the direct answer.{cond_note}\n\n"
            "After your answer, on a NEW line output ONLY: "
            "PAGES_USED: [comma-separated page numbers from the [SOURCE | Page: N] headers that directly support your answer]"
        )

    # Deterministic types — also request PAGES_USED for citation guidance
    return (
        f"{context}\n\n{question}\n\n"
        "After your answer, on a NEW line output ONLY: "
        "PAGES_USED: [comma-separated page numbers that support your answer]"
    )


# ---------------------------------------------------------------------------
# LLM call with streaming (Anthropic SDK)
# ---------------------------------------------------------------------------


def _is_rate_limit_error(exc: Exception) -> bool:
    """Check if exception is a rate limit or overloaded error."""
    import anthropic as _anthropic

    if isinstance(exc, _anthropic.RateLimitError):
        return True
    if isinstance(exc, _anthropic.APIStatusError) and exc.status_code == 529:
        return True
    return False


def _build_messages(user_message: str, conversation_history: "list[dict] | None") -> list:
    """Build Anthropic messages list, prepending multi-turn history if provided."""
    if not conversation_history:
        return [{"role": "user", "content": user_message}]
    messages = [{"role": t["role"], "content": t["content"]} for t in conversation_history]
    messages.append({"role": "user", "content": user_message})
    return messages


def _call_llm(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 512,
    model: str = MODEL,
    system_blocks: list[dict] | None = None,
    on_token=None,
    conversation_history: "list[dict] | None" = None,
) -> tuple[str, float, float, float, int, int]:
    """Call Claude via Anthropic SDK with streaming.

    Returns (answer_text, ttft_ms, total_ms, tpot_ms, input_tokens, output_tokens).
    Retries up to MAX_RETRIES times on transient failures, with extended
    exponential backoff (10s/30s/60s) for rate limit and overloaded errors.

    Args:
        system_prompt: System prompt text (used if system_blocks is None).
        user_message: User message text.
        max_tokens: Maximum tokens to generate.
        model: Model name.
        system_blocks: Optional list of system message blocks for multi-part
            caching. When provided, overrides system_prompt. Each block is a dict
            with 'type', 'text', and optional 'cache_control' keys.
    """
    global _ANTHROPIC_CREDITS_EXHAUSTED
    # Skip Anthropic SDK entirely if credits already known to be exhausted
    last_exc = None
    for attempt in range(1 + MAX_RETRIES):
        if attempt > 0:
            time.sleep(RETRY_DELAYS[attempt - 1])
        try:
            return _call_llm_once(
                system_prompt,
                user_message,
                max_tokens,
                model=model,
                system_blocks=system_blocks,
                on_token=on_token,
                conversation_history=conversation_history,
            )
        except Exception as exc:
            last_exc = exc
            logger.warning(f"[LLM] Attempt {attempt + 1} failed: {exc}")
            str(exc).lower()
            # On rate limit / overloaded, switch to longer backoff schedule
            if _is_rate_limit_error(exc):
                logger.warning("[LLM] Rate limit detected, switching to extended backoff")
                for rl_attempt in range(MAX_RETRIES_RATE_LIMIT):
                    time.sleep(RETRY_DELAYS_RATE_LIMIT[rl_attempt])
                    try:
                        return _call_llm_once(
                            system_prompt,
                            user_message,
                            max_tokens,
                            model=model,
                            system_blocks=system_blocks,
                            on_token=on_token,
                            conversation_history=conversation_history,
                        )
                    except Exception as rl_exc:
                        last_exc = rl_exc
                        logger.warning(
                            f"[LLM] Rate-limit retry {rl_attempt + 1}/{MAX_RETRIES_RATE_LIMIT} failed: {rl_exc}"
                        )
                raise last_exc
    # All retries exhausted
    raise last_exc


def _call_llm_once(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 512,
    model: str = MODEL,
    system_blocks: list[dict] | None = None,
    on_token=None,
    conversation_history: "list[dict] | None" = None,
) -> tuple[str, float, float, float, int, int]:
    """Single streaming LLM call.

    Args:
        system_blocks: Optional multi-block system prompt for granular caching.
            When provided, the first block (law context) has cache_control so it
            can be cached independently of the type-specific prompt that follows.
            This enables cache hits across different answer types for the same law.
        conversation_history: Optional prior Q&A turns for multi-turn context.
            Prepended as proper Anthropic multi-turn messages before the final user turn.
    """
    # LiteLLM proxy path — uses OpenAI-compatible streaming
    if _USE_LITELLM:
        from arlc.llm import litellm_backend

        return litellm_backend.call_llm(
            system_prompt,
            user_message,
            max_tokens,
            model=model,
            system_blocks=system_blocks,
            on_token=on_token,
        )

    client = _get_client()
    start = time.perf_counter()

    chunks: list[str] = []
    ttft_ms: float | None = None
    input_tokens = 0
    output_tokens = 0

    # Use multi-block system if provided, otherwise single-block with cache_control
    if system_blocks is not None:
        system_param = system_blocks
    else:
        system_param = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]

    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        temperature=0.0,
        system=system_param,
        messages=_build_messages(user_message, conversation_history),
    ) as stream:
        for text in stream.text_stream:
            if ttft_ms is None:
                ttft_ms = (time.perf_counter() - start) * 1000
            chunks.append(text)
            if on_token is not None:
                on_token(text)

        # Get final message for token counts
        final = stream.get_final_message()
        input_tokens = final.usage.input_tokens
        output_tokens = final.usage.output_tokens

    total_ms = (time.perf_counter() - start) * 1000
    if ttft_ms is None:
        ttft_ms = total_ms

    tpot_ms = (total_ms - ttft_ms) / max(output_tokens, 1)
    answer_text = "".join(chunks).strip()

    # Log cache info for debugging F metric optimization
    cache_read = getattr(final.usage, "cache_read_input_tokens", 0) or 0
    cache_create = getattr(final.usage, "cache_creation_input_tokens", 0) or 0
    if cache_read or cache_create:
        logger.info(
            f"[LLM] model={model} ttft={ttft_ms:.0f}ms "
            f"cache_read={cache_read} cache_create={cache_create} in={input_tokens}"
        )

    return answer_text, ttft_ms, total_ms, tpot_ms, input_tokens, output_tokens


# Tool schema for structured output: answer + page citations
_SUBMIT_ANSWER_TOOL = {
    "name": "submit_answer",
    "description": "Submit your answer with the page numbers that support it",
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {
                "type": "string",
                "description": "The answer to the question",
            },
            "pages_used": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    "Page numbers from the [PAGE N] or [SOURCE | Page: N] markers "
                    "in the provided context that directly support your answer. "
                    "Cite ONLY the minimal pages needed."
                ),
            },
        },
        "required": ["answer", "pages_used"],
    },
}


def _call_llm_structured(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 512,
    model: str = MODEL,
    system_blocks: list[dict] | None = None,
    on_token=None,
    conversation_history: "list[dict] | None" = None,
) -> tuple[str, list[int], float, float, float, int, int]:
    """LLM call with forced tool_use for structured answer + page citations.

    Returns (answer_text, pages_used, ttft_ms, total_ms, tpot_ms, input_tokens, output_tokens).
    Falls back to regular _call_llm if tool_use fails.
    """
    global _ANTHROPIC_CREDITS_EXHAUSTED

    if _ANTHROPIC_CREDITS_EXHAUSTED:
        raw, ttft, total, tpot, in_tok, out_tok = _call_llm(
            system_prompt,
            user_message,
            max_tokens,
            model=model,
            system_blocks=system_blocks,
            on_token=on_token,
            conversation_history=conversation_history,
        )
        pages = _extract_pages_used(raw)
        return raw, pages, ttft, total, tpot, in_tok, out_tok

    client = _get_client()
    start = time.perf_counter()
    ttft_ms = None
    input_tokens = 0
    output_tokens = 0

    if system_blocks is not None:
        system_param = system_blocks
    else:
        system_param = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0.0,
            system=system_param,
            messages=_build_messages(user_message, conversation_history),
            tools=[_SUBMIT_ANSWER_TOOL],
            tool_choice={"type": "tool", "name": "submit_answer"},
        )

        ttft_ms = (time.perf_counter() - start) * 1000
        total_ms = ttft_ms  # non-streaming, so ttft ≈ total
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        tpot_ms = total_ms / max(output_tokens, 1)

        # Extract tool_use result
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_answer":
                tool_input = block.input
                answer_text = tool_input.get("answer", "")
                pages_used = tool_input.get("pages_used", [])
                # Validate pages_used are integers
                pages_used = [int(p) for p in pages_used if isinstance(p, (int, float))]
                logger.info(f"[LLM] Structured output: answer={answer_text[:60]} pages={pages_used} model={model}")
                return answer_text, pages_used, ttft_ms, total_ms, tpot_ms, input_tokens, output_tokens

        # No tool_use block found — extract text content as fallback
        text_parts = [b.text for b in response.content if hasattr(b, "text")]
        raw = " ".join(text_parts).strip()
        pages = _extract_pages_used(raw)
        return raw, pages, ttft_ms, total_ms, tpot_ms, input_tokens, output_tokens

    except Exception as e:
        logger.warning(f"[LLM] Structured output failed: {e}, falling back to regular call")
        err_msg = str(e).lower()
        if "credit balance" in err_msg or "invalid x-api-key" in err_msg or "authentication_error" in err_msg:
            _ANTHROPIC_CREDITS_EXHAUSTED = True

        raw, ttft, total, tpot, in_tok, out_tok = _call_llm(
            system_prompt,
            user_message,
            max_tokens,
            model=model,
            system_blocks=system_blocks,
            on_token=on_token,
            conversation_history=conversation_history,
        )
        pages = _extract_pages_used(raw)
        return raw, pages, ttft, total, tpot, in_tok, out_tok


# ---------------------------------------------------------------------------
# Self-critique for free_text answers (second Opus call)
# ---------------------------------------------------------------------------


def _self_critique_free_text(question: str, answer: str, source_text: str) -> str:
    """Check answer against 5 scoring criteria; rewrite if any fail.

    Returns the original answer unchanged if all criteria pass, otherwise
    returns the rewritten answer. Uses Opus for evaluation quality.
    """
    is_case = any(
        kw in question.lower()
        for kw in [
            "case cfi",
            "case sct",
            "case arb",
            "case enf",
            "case ca ",
            "case dec",
            "arbitration case",
            "cfi ",
            "sct ",
            "arb ",
            " ca ",
        ]
    )
    char_target = "500-700 characters (STRICT MAXIMUM: 700)" if is_case else "500-650 characters (STRICT MAXIMUM: 700)"
    char_count = len(answer)

    critique_system = (
        "You are a strict evaluator scoring a legal QA answer against 5 binary criteria. "
        "Your job is to fix failures — be ruthless about character limits and opener quality."
    )
    source_excerpt = source_text[:2500] if source_text else "[no source]"
    critique_msg = (
        f"Question: {question}\n\n"
        f"Answer ({char_count} chars): {answer}\n\n"
        f"Source text (excerpt):\n{source_excerpt}\n\n"
        f"Evaluate each criterion strictly (YES/NO):\n"
        f"1. CORRECTNESS: Every factual claim matches the source text? No errors?\n"
        f"2. COMPLETENESS: ALL parts of the question are addressed?\n"
        f"3. GROUNDING: At least one verbatim quote in double quotes (≥10 chars) from the source?\n"
        f"4. CONFIDENCE: Definitive language for clear facts? Qualified only for genuine gaps in source?\n"
        f"5. CLARITY: First sentence is a direct factual statement? No markdown?\n"
        f"6. LENGTH: Answer is within {char_target}? Current: {char_count} chars.\n\n"
        f"If ALL six are YES: output ONLY the original answer text, unchanged.\n"
        f"If ANY is NO: rewrite to fix failures. Target {char_target}. "
        f"If too long, cut less important context — keep the verbatim quote and direct opener. "
        f"Start with a direct factual statement. No markdown.\n\n"
        f"Output ONLY the final answer text — no preamble, no criteria list."
    )
    try:
        raw, _, _, _, _, _ = _call_llm(critique_system, critique_msg, max_tokens=600, model=MODEL_FREE_TEXT)
        result = raw.strip()
        return result if result else answer
    except Exception as e:
        logger.warning(f"[Critique] Self-critique failed: {e}")
        return answer


# ---------------------------------------------------------------------------
# Answer parsing & normalization
# ---------------------------------------------------------------------------

_DATE_FORMATS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d %B %Y",
    "%B %d, %Y",
    "%d %b %Y",
    "%b %d, %Y",
    "%d-%m-%Y",
    "%B %Y",
    "%d.%m.%Y",
]


def _normalize_date(text: str) -> str | None:
    """Parse a date string and normalize to YYYY-MM-DD."""
    text = text.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _extract_pages_used(text: str) -> list[int]:
    """Extract page numbers from PAGES_USED: line in LLM output.

    Parses patterns like:
        PAGES_USED: 3, 7, 12
        PAGES_USED: [3, 7, 12]
        PAGES_USED: 3
    Returns empty list if not found or unparseable.
    """
    match = re.search(r"PAGES_USED:\s*\[?([^\]\n]+)\]?", text, re.I)
    if not match:
        return []
    raw = match.group(1).strip()
    pages = []
    for token in re.split(r"[,\s]+", raw):
        token = token.strip()
        if token.isdigit():
            pages.append(int(token))
    return pages


def _strip_llm_artifacts(text: str) -> str:
    """Remove SOURCES, PAGES, QUOTE lines, inline [N] markers, and trailing (Source: ...) tags."""
    text = re.sub(r"\n\s*SOURCES(?:\s+USED)?:\s*[^\n]*", "", text, flags=re.I).strip()
    text = re.sub(r"\n\s*PAGES?(?:_USED)?:\s*[^\n]*", "", text, flags=re.I | re.MULTILINE).strip()
    text = re.sub(r"\n\s*QUOTE:\s*[^\n]*", "", text, flags=re.I).strip()
    text = re.sub(r"\s*\[(\d+)\]", "", text).strip()
    # Remove trailing "(Source: Law Name, p.N)" tags — gold never uses them
    text = re.sub(r"\s*\(Source:\s*[^)]+\)\s*$", "", text, flags=re.I).strip()
    return text


def _truncate_free_text(text: str, limit: int = 705) -> str:
    """Truncate to last complete sentence within limit characters (safety net)."""
    if len(text) <= limit:
        return text
    window = text[:limit]
    # Find last sentence-ending punctuation followed by space or end-of-window
    for i in range(len(window) - 1, len(window) // 2, -1):
        c = window[i]
        if c in ".!?" and (i + 1 >= len(window) or window[i + 1] in " \n\"'"):
            return text[: i + 1].strip()
    # Fall back to last word boundary
    last_space = window.rfind(" ")
    if last_space > len(window) // 2:
        return text[:last_space].strip()
    return window.strip()


def _extract_grounding(response: str) -> list[dict]:
    """Parse the GROUNDING section from LLM response into structured claim→page mappings."""
    grounding: list[dict] = []
    match = re.search(r"GROUNDING:\s*\n(.*)", response, re.DOTALL)
    if not match:
        return grounding
    for line in match.group(1).strip().splitlines():
        line = line.strip().lstrip("-").strip()
        # Match patterns like: "[claim]" → page N  or  "claim" -> page N
        m = re.match(r'"(.+?)"\s*(?:→|->)\s*page\s+(\d+)', line, re.IGNORECASE)
        if m:
            grounding.append({"claim": m.group(1), "page": int(m.group(2))})
    return grounding


def _parse_answer(text: str, answer_type: str, web_mode: bool = False) -> object:
    """Convert raw LLM text to the correct Python type.

    Applies NFKC normalization and Cyrillic homoglyph cleanup on string answers
    so that Cyrillic lookalikes (е/o/р/с/x) don't break exact-match scoring.
    """
    text = _strip_llm_artifacts(text)

    if answer_type == "free_text":
        # Extract answer from CoT <answer> tags if present
        answer_match = re.search(r"<answer>\s*(.*?)\s*</answer>", text, re.DOTALL)
        if answer_match:
            text = answer_match.group(1).strip()
        elif "<analysis>" in text:
            # CoT truncated before <answer> — strip analysis tags, use content
            text = re.sub(r"</?analysis>", "", text).strip()
        # Safety net: always strip CoT tags that might survive extraction
        text = re.sub(r"</?(?:analysis|answer|thinking|scratchpad)>", "", text).strip()
        # Strip GROUNDING section if it leaked into the answer text
        text = re.sub(r"\s*GROUNDING:\s*\n.*", "", text, flags=re.DOTALL).strip()
        # Detect leaked numbered CoT format (e.g. "1. QUESTION PARSE:..." / "1. OUTCOME:...")
        # This happens when max_tokens truncates before <answer> tags and no <analysis> tags present
        if re.match(
            r"^\d+\.\s*(?:QUESTION PARSE|KEY PROVISIONS|CONDITIONS CHECK|GAPS|DRAFT|OUTCOME|ORDER|RULING)", text
        ):
            # Try to extract the DRAFT or OUTCOME section content (the actual answer)
            draft_match = re.search(
                r"(?:5\.\s*DRAFT|OUTCOME|ORDER|RULING)[:\s]*\n?(.*?)(?:\n\d+\.\s*[A-Z]|\Z)",
                text,
                re.DOTALL,
            )
            if draft_match:
                text = draft_match.group(1).strip()
            else:
                # Last resort: extract the last numbered section's content
                sections = re.split(r"\n\d+\.\s*[A-Z][A-Z\s]+:", text)
                if len(sections) > 1:
                    text = sections[-1].strip()
        clean = text.strip()
        if clean.lower() in ("null", "none", "n/a", "not available"):
            return "The information is not available in the provided documents."
        # Competition mode: strip markdown and enforce char limit.
        # Web mode: preserve markdown formatting and allow unlimited length.
        if not web_mode:
            clean = re.sub(r"\*\*(.+?)\*\*", r"\1", clean)
            clean = re.sub(r"\*(.+?)\*", r"\1", clean)
            if len(clean) > 705:
                clean = _truncate_free_text(clean, limit=705)
        return clean

    stripped = text.strip().rstrip(".")

    if answer_type == "boolean":
        lower = stripped.lower()
        if lower == "true" or lower.startswith("true"):
            return True
        if lower == "false" or lower.startswith("false"):
            return False
        return None

    if answer_type == "number":
        if stripped.lower() == "null":
            return None
        cleaned = stripped
        for prefix in ("AED", "USD", "GBP", "EUR", "$", "£", "€"):
            cleaned = cleaned.replace(prefix, "").strip()
        # Handle space-separated thousands: "1 000 000" -> "1000000"
        digits_only = cleaned.replace(",", "").replace(" ", "")
        if digits_only and re.match(r"^[\d.]+$", digits_only):
            cleaned = digits_only
        else:
            cleaned = cleaned.split()[0] if cleaned.split() else cleaned
        try:
            val = float(cleaned.replace(",", ""))
            return int(val) if val == int(val) else val
        except (ValueError, OverflowError):
            return None

    if answer_type == "names":
        first_line = stripped.split("\n")[0].strip().rstrip(".")
        if first_line.lower() in ("null", "none", "n/a", "not available", ""):
            return None
        # Prefer numbered party markers (1), (2) as delimiters (preserves company names with commas)
        if re.search(r"\(\d+\)", first_line):
            parts = [re.sub(r"^\(\d+\)\s*", "", p).strip() for p in re.split(r"(?=\(\d+\))", first_line) if p.strip()]
            parts = [p for p in parts if p]
        elif "," not in first_line and " and " in first_line.lower():
            parts = [n.strip() for n in re.split(r"\s+and\s+", first_line, flags=re.I) if n.strip()]
        else:
            # Smart comma split: don't split after "CO." or before "LTD/LLC/INC/P.J.S.C"
            # "A.P.F. GROUP CO., LTD" should stay together (CO. in lookbehind + LTD in lookahead)
            # "COMPANY P.J.S.C, OTHER CO" SHOULD split (P.J.S.C is a company suffix, not mid-name)
            # The lookahead (?!P.J.S.C) already prevents splitting BEFORE P.J.S.C suffix,
            # so the old (?<!P.J.S.C) lookbehind was overly restrictive and was removed.
            parts = [
                n.strip()
                for n in re.split(
                    r"(?<!CO)(?<!CO\.)(?<!L\.L\.C),\s*(?!(?:LTD|LLC|L\.L\.C|INC|PLC|PJSC|P\.J\.S\.C)\b)",
                    first_line,
                    flags=re.I,
                )
                if n.strip()
            ]

        # Guard against malformed LLM prose being split into a fake names list.
        # If any element looks like prose (contains "Based on", "document", markdown
        # formatting, or is excessively long), the LLM returned free-text instead
        # of a clean names list. Try to extract actual names from the full text,
        # or fall back to None.
        _PROSE_MARKERS = ["based on", "document", "the court", "according to"]

        def _is_malformed(part: str) -> bool:
            p_lower = part.lower()
            return any(m in p_lower for m in _PROSE_MARKERS) or "**" in part or len(part) > 100

        if any(_is_malformed(p) for p in parts):
            # Try to salvage: look for ALL-CAPS names or quoted names in the full text
            # Common patterns: "JOHN SMITH", 'Jane Doe Ltd'
            full_text = re.sub(r"\*\*", "", stripped)  # remove markdown
            caps_names = re.findall(r"\b([A-Z][A-Z\s\.]{3,}[A-Z])\b", full_text)
            if caps_names:
                # Deduplicate preserving order
                seen = set()
                parts = []
                for n in caps_names:
                    n_clean = n.strip()
                    if n_clean not in seen and len(n_clean) <= 100:
                        seen.add(n_clean)
                        parts.append(n_clean)
            else:
                # Could not extract — return None to avoid garbage answers
                return None

        # NFKC + homoglyph normalization for names
        return [check_homoglyphs(unicodedata.normalize("NFKC", n)) for n in parts]

    if answer_type == "date":
        first_line_date = stripped.split("\n")[0].strip().rstrip(".")
        if first_line_date.lower() in ("null", "none", "n/a", "not available", ""):
            return None
        # Try to extract a YYYY-MM-DD pattern from the first line in case LLM adds explanation
        iso_match = re.search(r"\d{4}-\d{2}-\d{2}", first_line_date)
        if iso_match:
            candidate = iso_match.group(0)
            normalized = _normalize_date(candidate)
            if normalized:
                return normalized
        return _normalize_date(first_line_date) or first_line_date

    if answer_type == "name":

        def _normalize_case_id(s: str) -> str:
            """Normalize case ID separators, preserving sub-case designators.

            'ENF-316-2023/2' → 'ENF-316-2023/2' (has sub-case /2, preserve original)
            'ENF-316-2023'   → 'ENF 316/2023'   (standard normalization)
            """
            m = re.match(
                r"^(CFI|SCT|CA|ARB|ENF|DEC|TCD|ACT)[- ]?(\d+)[- /](\d{4})(?:[/\-](\d+))?$",
                s.strip(),
                re.IGNORECASE,
            )
            if m:
                if m.group(4):
                    # Has sub-case designator (e.g. /2) — preserve original format
                    # Source documents use specific formats like "ENF-316-2023/2"
                    return s.strip()
                # Preserve leading zeros (e.g. ARB 034/2025, CFI 010/2024)
                return f"{m.group(1).upper()} {m.group(2)}/{m.group(3)}"
            return s

        lines = [line.strip().rstrip(".") for line in stripped.split("\n") if line.strip()]
        if not lines:
            return None

        # For chain-of-thought: look for case ID on last line
        last_line = lines[-1]
        case_full = re.search(r"(?:CFI|CA|ARB|ENF|SCT|TCD|DEC|ACT)\s*\d+/\d{4}", last_line, re.I)
        if case_full and len(lines) > 1:
            return _normalize_case_id(case_full.group(0))
        # Search full text for case ID
        if len(lines) > 1:
            full_case = re.search(r"(?:CFI|CA|ARB|ENF|SCT|TCD|DEC|ACT)\s*\d+/\d{4}", stripped, re.I)
            if full_case:
                return full_case.group(0)
        # Fallback: partial case ID on last line (may have dashes instead of slashes)
        partial_case = re.search(r"(?:CFI|CA|ARB|ENF|SCT|TCD|DEC|ACT)[\s\-_]*\d+[\s/\-_]*\d+", last_line, re.I)
        if partial_case and len(lines) > 1:
            return _normalize_case_id(partial_case.group(0))

        first_line = lines[0]
        null_phrases = (
            "null",
            "none",
            "n/a",
            "not found",
            "not available",
            "i cannot",
            "i don't",
            "cannot answer",
            "not provided",
            "not mentioned",
            "not specified",
            "not stated",
            "i have carefully",
            "the document",
            "the documents",
            "based on the",
            "no information",
        )
        if any(first_line.lower().startswith(p) or first_line.lower() == p for p in null_phrases):
            return None
        first_line = re.sub(r"\*\*(.+?)\*\*", r"\1", first_line)
        # If explanatory, try to extract case ID
        case_match = re.search(r"(?:CFI|CA|ARB|ENF|SCT|TCD|DEC)[\s\-_]*\d+[\s/\-_]*\d+", first_line, re.I)
        if case_match and len(first_line) > 30:
            return _normalize_case_id(case_match.group(0))
        return _normalize_case_id(first_line) if first_line else None

    return stripped if stripped else None


# ---------------------------------------------------------------------------
# Mega-context for law questions
# ---------------------------------------------------------------------------

_LAW_CONTEXTS: dict[str, str] = {}


def _clean_law_pages(pages_text: list[str]) -> list[str]:
    """Remove repeated headers/footers and near-empty pages from law PDF text.

    Zero-regression: only strips exact-duplicate lines appearing on 50%+ of pages
    and collapses excessive whitespace. No substantive content is removed.
    """
    if len(pages_text) < 3:
        return pages_text

    # Detect repeated first lines (headers) across pages
    first_lines = [t.split("\n")[0].strip() for t in pages_text if t.strip()]
    first_counts = Counter(first_lines)
    repeated_headers = {
        line for line, count in first_counts.items() if count >= len(pages_text) * 0.5 and len(line) > 5
    }

    # Detect repeated last lines (footers) across pages
    last_lines = []
    for t in pages_text:
        stripped_lines = [line for line in t.split("\n") if line.strip()]
        if stripped_lines:
            last_lines.append(stripped_lines[-1].strip())
    last_counts = Counter(last_lines)
    repeated_footers = {line for line, count in last_counts.items() if count >= len(pages_text) * 0.5 and len(line) > 5}

    cleaned = []
    for text in pages_text:
        lines = text.split("\n")
        # Strip repeated header (first line)
        if lines and lines[0].strip() in repeated_headers:
            lines = lines[1:]
        # Strip repeated footer (last non-empty line)
        while lines and not lines[-1].strip():
            lines.pop()
        if lines and lines[-1].strip() in repeated_footers:
            lines.pop()
        # Collapse multiple blank lines
        result = "\n".join(lines)
        result = re.sub(r"\n{3,}", "\n\n", result)
        # Skip near-empty pages (< 50 chars of content)
        if len(result.strip()) >= 50:
            cleaned.append(result.strip())
    return cleaned


def _get_law_context(pdf_id: str) -> str:
    """Load full text of a law document with [PAGE N] markers. Cached."""
    if pdf_id in _LAW_CONTEXTS:
        return _LAW_CONTEXTS[pdf_id]

    path = os.path.join(_DATA_DIR, "documents", f"{pdf_id}.pdf")
    if not os.path.exists(path):
        _LAW_CONTEXTS[pdf_id] = ""
        return ""

    doc = None
    try:
        doc = pymupdf.open(path)
        title = doc[0].get_text().strip()[:200]
        page_count = len(doc)

        # Collect raw page texts for cleaning
        raw_pages: list[tuple[int, str]] = []
        for p in range(page_count):
            text = doc[p].get_text().strip()
            if text:
                raw_pages.append((p + 1, text))

        # Detect repeated headers/footers across all pages
        all_texts = [t for _, t in raw_pages]
        first_lines_count = Counter(t.split("\n")[0].strip() for t in all_texts if t.strip())
        repeated_headers = {
            line for line, count in first_lines_count.items() if count >= len(all_texts) * 0.5 and len(line) > 5
        }
        last_nz_lines = []
        for t in all_texts:
            stripped = [ln for ln in t.split("\n") if ln.strip()]
            if stripped:
                last_nz_lines.append(stripped[-1].strip())
        last_lines_count = Counter(last_nz_lines)
        repeated_footers = {
            line for line, count in last_lines_count.items() if count >= len(all_texts) * 0.5 and len(line) > 5
        }

        # Clean each page and rebuild with [PAGE N] markers
        parts = [f"=== {title[:100]} ===\n"]
        for page_num, text in raw_pages:
            lines = text.split("\n")
            if lines and lines[0].strip() in repeated_headers:
                lines = lines[1:]
            while lines and not lines[-1].strip():
                lines.pop()
            if lines and lines[-1].strip() in repeated_footers:
                lines.pop()
            result = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
            if len(result.strip()) >= 50:
                parts.append(f"[PAGE {page_num}]\n{result.strip()}\n")

        _LAW_CONTEXTS[pdf_id] = "\n".join(parts)
        logger.info(f"[LawCtx] Loaded {pdf_id[:16]}: {page_count} pages, {len(parts) - 1} after cleaning")
    except Exception as e:
        logger.warning(f"[LawCtx] Failed {pdf_id[:16]}: {e}")
        _LAW_CONTEXTS[pdf_id] = ""
    finally:
        if doc is not None:
            doc.close()

    return _LAW_CONTEXTS[pdf_id]


def _get_law_pages_context(pdf_id: str, pages: list[int]) -> str:
    """Load specific pages from a law PDF with [PAGE N] markers.

    Used for amendment questions where only cover pages (page 1) are needed
    to avoid loading 9 full PDFs (~950K chars) which causes timeouts/context overflow.
    """
    path = os.path.join(_DATA_DIR, "documents", f"{pdf_id}.pdf")
    if not os.path.exists(path):
        return ""
    try:
        doc = pymupdf.open(path)
        title = doc[0].get_text().strip().split("\n")[0][:80]
        parts = [f"=== {title} ==="]
        for p in pages:
            if 1 <= p <= len(doc):
                text = doc[p - 1].get_text().strip()
                if text:
                    parts.append(f"[PAGE {p}]\n{text}")
        doc.close()
        return "\n".join(parts) if len(parts) > 1 else ""
    except Exception:
        return ""


# Page-cap constant: max pages per law doc in windowed context
_LAW_PAGE_CAP = 15


def _get_retriever_windowed_context(
    law_pdf_ids: list[str],
    source_pages: list[dict],
) -> str:
    """Build law context using retriever-guided windowing.

    Uses the retriever's source_pages (BM25 + vector + cross-encoder) to find
    the most relevant pages, then expands with ±2 window. Falls back to full
    PDF if no retriever data for a doc.

    Strategy per law doc:
    1. Get retriever's pages for this doc (proven accurate via cross-encoder)
    2. Add page 1 (cover/title) for structural context
    3. Add TOC pages (3-4) for large docs
    4. Expand retriever pages ±2 to catch page-spanning content
    5. Fallback: load full PDF if no retriever pages found
    """
    all_parts: list[str] = []
    for pid in law_pdf_ids:
        # Find retriever's pages for this doc
        retriever_pages = {
            sp["page_number"] for sp in source_pages if sp.get("doc_id") == pid and sp.get("page_number")
        }

        if not retriever_pages:
            # No retriever data — load full doc (safe fallback)
            ctx = _get_law_context(pid)
        else:
            # Get page count from article index or PDF
            doc_info = _ARTICLE_INDEX.get(pid, {})
            page_count = doc_info.get("page_count", 999)

            # Build window: cover page + TOC + retriever pages ± 2
            pages_to_load: set[int] = {1}  # Always include cover page

            # Add TOC pages for large docs (usually pages 3-4 in DIFC laws)
            if page_count > 10:
                pages_to_load.update([3, 4])

            # Add retriever pages ± 2
            for rp in retriever_pages:
                for offset in range(-2, 3):  # -2, -1, 0, +1, +2
                    p = rp + offset
                    if 1 <= p <= page_count:
                        pages_to_load.add(p)

            ctx = _get_law_pages(pid, sorted(pages_to_load))

        if ctx:
            all_parts.append(ctx)

    return "\n\n".join(all_parts)


def _get_law_pages(pdf_id: str, pages: list[int]) -> str:
    """Load specific pages from a law PDF with [PAGE N] markers."""
    path = os.path.join(_DATA_DIR, "documents", f"{pdf_id}.pdf")
    if not os.path.exists(path):
        return ""

    doc = None
    try:
        doc = pymupdf.open(path)
        title = doc[0].get_text().strip()[:200]
        parts = [f"=== {title[:100]} ===\n"]
        for p in pages:
            if 1 <= p <= len(doc):
                text = doc[p - 1].get_text().strip()
                if text:
                    parts.append(f"[PAGE {p}]\n{text}\n")
        logger.info(f"[LawCtx] Windowed {pdf_id[:16]}: {len(pages)} pages (of {len(doc)} total)")
        return "\n".join(parts)
    except Exception as e:
        logger.warning(f"[LawCtx] Failed {pdf_id[:16]}: {e}")
        return ""
    finally:
        if doc is not None:
            doc.close()


# Law routing from question text
_LAW_NAME_TO_PDF: dict[str, str] = {}
_LAW_DYNAMIC_TITLES: dict[str, str] = {}
_LAW_MAPPING_BUILT = False


def _build_law_name_mapping():
    """Build mapping from law keywords to PDF IDs."""
    global _LAW_NAME_TO_PDF, _LAW_DYNAMIC_TITLES, _LAW_MAPPING_BUILT
    if _LAW_MAPPING_BUILT:
        return
    _LAW_MAPPING_BUILT = True

    keywords = {
        "employment": ["employment law", "employment rights"],
        "trust": ["trust law", "difc trust"],
        "foundation": ["foundations law", "foundation law"],
        "personal property": ["personal property law"],
        "operating": ["operating law", "law no. 7"],
        "crs": ["common reporting standard", "crs law"],
        "general partnership": ["general partnership law", "gp law"],
        "limited liability partnership": ["limited liability partnership law", "llp law"],
        "civil": ["civil and commercial", "application of civil"],
    }

    _TITLE_STOP = {
        "difc",
        "law",
        "no",
        "of",
        "the",
        "and",
        "for",
        "a",
        "an",
        "regulations",
        "regulation",
        "rules",
        "rule",
        "code",
        "act",
        "consolidated",
        "version",
        "amended",
        "updated",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "january",
        "february",
    }

    for pdf_id, info in _ARTICLE_INDEX.items():
        if info.get("type") != "LAW":
            continue
        path = os.path.join(_DATA_DIR, "documents", f"{pdf_id}.pdf")
        if not os.path.exists(path):
            continue
        doc = None
        try:
            doc = pymupdf.open(path)
            title_text = doc[0].get_text()[:500].lower()

            for key, patterns in keywords.items():
                if any(p in title_text for p in patterns):
                    _LAW_NAME_TO_PDF[key] = pdf_id
                    break

            # Dynamic title fragments for laws not in hardcoded groups
            core_title = re.split(r"\bconsolidated\b|\bversion\b|\bamended\b", title_text[:200])[0].strip()
            title_words = [
                w
                for w in re.split(r"[\W_]+", core_title)
                if len(w) > 2 and w.lower() not in _TITLE_STOP and not w.isdigit()
            ]
            for i, word in enumerate(title_words[:6]):
                w = word.lower()
                if len(w) > 3 and w not in _LAW_DYNAMIC_TITLES:
                    _LAW_DYNAMIC_TITLES[w] = pdf_id
                if i + 1 < len(title_words):
                    bigram = f"{word} {title_words[i + 1]}".lower()
                    if bigram not in _LAW_DYNAMIC_TITLES:
                        _LAW_DYNAMIC_TITLES[bigram] = pdf_id
        except Exception:
            pass
        finally:
            if doc is not None:
                doc.close()

    logger.info(f"[LawRouter] {len(_LAW_NAME_TO_PDF)} hardcoded + {len(_LAW_DYNAMIC_TITLES)} dynamic")


def _identify_law_from_question(question: str) -> str | None:
    """Identify which DIFC law a question refers to. Returns pdf_id or None."""
    _build_law_name_mapping()
    q_lower = question.lower()

    law_patterns = {
        "employment": ["employment law", "employment", "difc law no. 2 of 2019"],
        "trust": ["trust law", "difc trust law", "difc law no. 4 of 2018"],
        "foundation": ["foundations law", "foundation", "difc law no. 3 of 2018"],
        "personal property": ["personal property law", "difc law no. 9", "personal property"],
        "operating": ["operating law", "difc law no. 7", "operating law 2018"],
        "crs": ["common reporting standard", "crs law", "crs", "difc law no. 2 of 2018"],
        "general partnership": ["general partnership law", "general partnership", "gp law", "difc law no. 11"],
        "limited liability partnership": [
            "limited liability partnership law",
            "limited liability partnership",
            "llp law",
            "difc law no. 5 of 2004",
        ],
        "civil": ["civil and commercial laws", "application of civil", "civil and commercial"],
    }
    for key, patterns in law_patterns.items():
        if any(p in q_lower for p in patterns):
            return _LAW_NAME_TO_PDF.get(key)

    # Dynamic title matching (longer fragments first for specificity)
    for fragment, pdf_id in sorted(_LAW_DYNAMIC_TITLES.items(), key=lambda x: -len(x[0])):
        if fragment in q_lower:
            return pdf_id

    # Article-based lookup
    art_match = re.search(r"article\s+(\d+)", question, re.I)
    if art_match:
        art_num = int(art_match.group(1))
        art_key = f"article_{art_num}"
        for pdf_id, info in _ARTICLE_INDEX.items():
            if info.get("type") == "LAW" and art_key in info.get("articles", {}):
                return pdf_id

    return None


def _is_pure_law_question(question: str) -> bool:
    """True if question has no case ID references."""
    return not bool(_CASE_ID_PATTERN.search(question))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def generate_answer(
    question: str,
    answer_type: str,
    source_pages: list[dict],
    question_id: str = "",
    metadata_answer: object = None,
    force_model: str | None = None,
    on_token=None,
    web_mode: bool = False,
    conversation_history: "list[dict] | None" = None,
) -> AnswerResult:
    """Generate an answer for a DIFC legal question.

    Args:
        question: The question text.
        answer_type: One of boolean, number, name, names, date, free_text.
        source_pages: Pre-selected pages [{"doc_id": "...", "page_number": N, "text": "..."}].
        question_id: Optional question ID for logging.
        metadata_answer: Pre-computed answer from router (skips LLM for non-free_text).
        force_model: Override the default LLM model.
        on_token: Streaming callback for token-by-token output (web mode).
        web_mode: When True, preserves markdown formatting in free_text answers
            and removes the character limit. Affects _get_system_prompt (adds markdown
            instructions) and _parse_answer (skips ** stripping and 705-char cap).
            Only meaningful for free_text answer_type.

    Returns:
        AnswerResult with answer, citations, and performance metrics.
    """
    qid_short = question_id[:12] if question_id else "?"
    logger.info(f"[{qid_short}] type={answer_type} pages={len(source_pages)}")

    # 0. Router metadata_answer fast path (pre-computed by router.py)
    # Guard: skip for free_text — metadata_answer is a bare case ID string,
    # not a detailed analysis. Free_text needs full LLM generation.
    if metadata_answer is not None and answer_type != "free_text":
        logger.info(f"[{qid_short}] Router metadata_answer hit: {metadata_answer}")
        # Build chunk_pages from source_pages
        pages = []
        seen = set()
        for sp in source_pages:
            did = sp.get("doc_id", "")
            pn = sp.get("page_number", 1)
            if did and did not in seen:
                pages.append({"doc_id": did, "page_numbers": [pn]})
                seen.add(did)
        return AnswerResult(answer=metadata_answer, chunk_pages=pages)

    # 1. Oracle fast path for deterministic case metadata
    oracle_result = _lookup_oracle(question, answer_type, source_pages)
    if oracle_result is not None:
        logger.info(f"[{qid_short}] Oracle hit: {oracle_result.answer}")
        return oracle_result

    # Decompose disabled: 30% free_text questions → PPQ=1.30 exactly at limit.
    # Any retry would push PPQ > 1.3, triggering platform F penalty.
    _sub_questions = ""

    # 2. Mega-context path for pure law questions
    if _is_pure_law_question(question):
        # General multi-law detection: extract all unique law doc_ids from source_pages
        # AND from the question text (via router) to catch multi-law references
        # even when retriever only returns pages from one law.
        law_pdf_ids: list[str] = []
        _seen_law_docs = set()
        for sp in source_pages:
            did = sp.get("doc_id", "")
            if did and did not in _seen_law_docs:
                # Check if this doc_id is a law document (not a case)
                doc_info = _ARTICLE_INDEX.get(did, {})
                if doc_info.get("type") == "LAW" or doc_info.get("articles"):
                    _seen_law_docs.add(did)
                    law_pdf_ids.append(did)
        # Also extract law doc_ids from the question text via router
        # This catches multi-law questions where retriever only returns one law's pages
        try:
            from arlc.router import route as _route_fn

            _route_result = _route_fn(question, answer_type)
            if _route_result.target_doc_ids:
                for _rdid in _route_result.target_doc_ids:
                    if _rdid not in _seen_law_docs:
                        doc_info = _ARTICLE_INDEX.get(_rdid, {})
                        if doc_info.get("type") == "LAW" or doc_info.get("articles"):
                            _seen_law_docs.add(_rdid)
                            law_pdf_ids.append(_rdid)
        except Exception:
            pass  # Router import failure is not fatal
        if not law_pdf_ids:
            single_id = _identify_law_from_question(question)
            if single_id:
                law_pdf_ids = [single_id]
        law_pdf_id = law_pdf_ids[0] if law_pdf_ids else None
        if law_pdf_ids:
            # Use full PDF context (proven approach, G=0.957).
            # Both article-index windowing and retriever-guided windowing were tried
            # but caused regressions (6 None answers, 2 boolean flips).
            # Exception: when 4+ law docs are targeted (amendment-type questions like
            # "Which laws were amended by Law No. X?"), loading all full PDFs would
            # be ~950K chars and exceed the context window / cause timeouts.
            # Instead, use only cover pages (page 1) which list amendment history.
            if len(law_pdf_ids) >= 4:
                law_context = "\n\n".join(ctx for pid in law_pdf_ids if (ctx := _get_law_pages_context(pid, [1])))
            else:
                law_context = "\n\n".join(ctx for pid in law_pdf_ids if (ctx := _get_law_context(pid)))
            if law_context:
                system = _get_system_prompt(question, answer_type, web_mode=web_mode)
                max_tok = _get_max_tokens(answer_type)

                # Build user message with law context instead of source pages
                if answer_type == "free_text":
                    user_msg = _build_user_message(question, law_context, answer_type, sub_questions=_sub_questions)
                else:
                    type_instructions = {
                        "boolean": "Answer with ONLY 'True' or 'False'. No explanation.",
                        "number": "Answer with ONLY the numeric value. No units, no explanation.",
                        "date": "Answer with ONLY the date in YYYY-MM-DD format. No explanation.",
                        "name": "Answer with ONLY the name or case ID. No explanation.",
                        "names": "Answer with ONLY the names as comma-separated values. No explanation.",
                    }
                    instruction = type_instructions.get(answer_type, "")
                    user_msg = f"{question}\n\n{instruction}"

                # Add retrieval-based attention hint to user message
                if source_pages:
                    hint_pages = ", ".join(str(sp["page_number"]) for sp in source_pages[:3] if sp.get("page_number"))
                    if hint_pages:
                        user_msg = (
                            f"[Retrieval hint: the most relevant content is likely near page(s) "
                            f"{hint_pages}. Verify against the full document.]\n\n{user_msg}"
                        )

                # LLM-guided page citation: ask the model to report which pages
                # from the law context it actually used to construct its answer.
                # These are used to build more precise chunk_pages citations.
                user_msg += (
                    "\n\nAfter your answer, on a NEW line output ONLY: "
                    "PAGES_USED: [comma-separated page numbers from the [PAGE N] "
                    "markers in the document that directly support your answer]"
                )

                # Build multi-block system prompt for granular caching.
                # Block 1: Law context (large, cacheable) — cached independently of
                #   answer_type so that boolean, number, free_text questions about the
                #   SAME law all share the cache, reducing TTFT from ~1500ms to ~300ms.
                # Block 2: Type-specific system prompt (small, varies per answer_type).
                law_context_block = {
                    "type": "text",
                    "text": (
                        "Here is the COMPLETE text of the relevant DIFC Law:\n\n"
                        f"{law_context}\n\n"
                        "Cite specific article numbers. Quote article text verbatim when relevant."
                    ),
                    "cache_control": {"type": "ephemeral"},
                }
                type_prompt_block = {
                    "type": "text",
                    "text": system,
                }
                system_blocks = [law_context_block, type_prompt_block]

                try:
                    ft_model = force_model or (MODEL_FREE_TEXT if answer_type == "free_text" else MODEL)
                    raw, llm_pages, ttft, total, tpot, in_tok, out_tok = _call_llm_structured(
                        "",
                        user_msg,
                        max_tok,
                        model=ft_model,
                        system_blocks=system_blocks,
                    )

                    parsed = _parse_answer(raw, answer_type, web_mode=web_mode)

                    # Build chunk_pages: prefer LLM-identified pages (the model
                    # knows which [PAGE N] sections it actually referenced).
                    # Fall back to retriever source pages if LLM didn't output
                    # PAGES_USED or returned empty/invalid pages.
                    chunk_pages = []
                    if llm_pages and law_pdf_ids:
                        # LLM told us which pages it used — map to doc_ids.
                        # For single-law questions, all pages belong to the primary doc.
                        # For multi-law, best-effort: assign to first law doc.
                        primary_doc = law_pdf_ids[0]
                        chunk_pages = [{"doc_id": primary_doc, "page_numbers": sorted(set(llm_pages))}]
                        logger.info(f"[{qid_short}] LLM-guided pages: {llm_pages}")
                    elif source_pages:
                        _pbd: dict[str, list[int]] = {}
                        for sp in source_pages:
                            did = sp.get("doc_id", "")
                            pn = sp.get("page_number", 1)
                            if did not in _pbd:
                                _pbd[did] = []
                            if pn not in _pbd[did]:
                                _pbd[did].append(pn)
                        chunk_pages = [{"doc_id": did, "page_numbers": sorted(pgs)} for did, pgs in _pbd.items()]
                    if not chunk_pages and law_pdf_id:
                        chunk_pages = [{"doc_id": law_pdf_id, "page_numbers": [1]}]
                    logger.info(
                        f"[{qid_short}] MegaCtx answer={str(parsed)[:60]} "
                        f"ttft={ttft:.0f}ms total={total:.0f}ms model={ft_model}"
                    )
                    return AnswerResult(
                        answer=parsed,
                        chunk_pages=chunk_pages,
                        ttft_ms=ttft,
                        total_time_ms=total,
                        tpot_ms=tpot,
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        model_name=f"{ft_model}_cached",
                    )
                except Exception as e:
                    logger.warning(f"[{qid_short}] MegaCtx failed: {e}, falling back to RAG")

    # 3. Standard RAG path — use pre-selected source pages
    context = _build_context(source_pages, question)
    if not context and not _is_trick_question(question):
        logger.warning(f"[{qid_short}] No context available")
        return AnswerResult(
            answer=None
            if answer_type != "free_text"
            else "The information is not available in the provided documents.",
            chunk_pages=[
                {"doc_id": p["doc_id"], "page_numbers": [p["page_number"]], "text": p.get("text")} for p in source_pages
            ]
            if source_pages
            else [],
        )

    system = _get_system_prompt(question, answer_type, web_mode=web_mode)
    max_tok = _get_max_tokens(answer_type)
    user_msg = _build_user_message(question, context, answer_type, sub_questions=_sub_questions)

    ft_model = force_model or (MODEL_FREE_TEXT if answer_type == "free_text" else MODEL)
    if on_token is not None:
        import asyncio as _asyncio

        raw, llm_pages, ttft, total, tpot, in_tok, out_tok = await _asyncio.to_thread(
            _call_llm_structured,
            system,
            user_msg,
            max_tok,
            model=ft_model,
            on_token=on_token,
            conversation_history=conversation_history,
        )
    else:
        raw, llm_pages, ttft, total, tpot, in_tok, out_tok = _call_llm_structured(
            system,
            user_msg,
            max_tok,
            model=ft_model,
            conversation_history=conversation_history,
        )

    parsed = _parse_answer(raw, answer_type, web_mode=web_mode)
    grounding = _extract_grounding(raw) if answer_type == "free_text" else []

    # Build chunk_pages: prefer LLM-identified pages for RAG path.
    # The LLM sees [SOURCE N | Page: P] headers and reports which pages
    # it actually used. Filter source_pages to only those the LLM cited.
    if llm_pages and source_pages:
        # Filter source_pages to only LLM-cited pages
        llm_page_set = set(llm_pages)
        filtered = [sp for sp in source_pages if sp.get("page_number") in llm_page_set]
        if filtered:
            logger.info(f"[{qid_short}] LLM-guided RAG pages: {llm_pages} (from {len(source_pages)} sources)")
            source_pages_for_cite = filtered
        else:
            # LLM cited pages not in source_pages — fall back
            source_pages_for_cite = source_pages
    else:
        source_pages_for_cite = source_pages

    # Build chunk_pages from (filtered) source_pages (deduplicate by doc)
    pages_by_doc: dict[str, list[int]] = {}
    for p in source_pages_for_cite:
        did = p["doc_id"]
        pn = p["page_number"]
        if did not in pages_by_doc:
            pages_by_doc[did] = []
        if pn not in pages_by_doc[did]:
            pages_by_doc[did].append(pn)
    chunk_pages = [{"doc_id": did, "page_numbers": sorted(pgs)} for did, pgs in pages_by_doc.items()]

    logger.info(
        f"[{qid_short}] RAG answer={str(parsed)[:60]} "
        f"ttft={ttft:.0f}ms total={total:.0f}ms in={in_tok} out={out_tok} model={ft_model}"
    )
    return AnswerResult(
        answer=parsed,
        chunk_pages=chunk_pages,
        ttft_ms=ttft,
        total_time_ms=total,
        tpot_ms=tpot,
        input_tokens=in_tok,
        output_tokens=out_tok,
        model_name=ft_model,
        grounding=grounding,
    )
