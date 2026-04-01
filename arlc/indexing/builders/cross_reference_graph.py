# Cross-reference graph concept from IndexRAG (Bao & Shi, 2026, arXiv:2603.16415)
"""Build a cross-reference graph by scanning all document pages for references.

Extracts:
- Internal references: "Article 15", "Section 3", "Schedule 1", "Part 2"
- External law references: "DIFC Law No. X of YYYY", "[Name] Law"
- Case references: "CFI 043/2020", "ARB 031/2025"
- RDC/court rule references: "RDC 44.8", "Rule 44.29"
- Bridge entities: entities appearing in 2+ documents

Output: data/cross_reference_graph.json

Usage:
    python build_cross_reference_graph.py
"""

import json
import re
from collections import defaultdict
from pathlib import Path

import pymupdf

DOCS_DIR = Path("data/documents")
DOCLING_DIR = Path("data/documents_md")
OUTPUT = Path("data/cross_reference_graph.json")

# --- Index files (optional, used for resolving references) ---
LAW_NAME_INDEX_PATH = Path("data/law_name_index.json")
ARTICLE_PAGE_INDEX_PATH = Path("data/article_page_index.json")

# --- Reference patterns ---

# Internal article/section/schedule/part references
INTERNAL_ARTICLE_RE = re.compile(
    r"\b(?:Article|Art\.)\s+(\d+[A-Z]?)(?:\((\d+)\))?",
    re.IGNORECASE,
)
INTERNAL_SECTION_RE = re.compile(
    r"\bSection\s+(\d+[A-Z]?)(?:\((\d+)\))?",
    re.IGNORECASE,
)
INTERNAL_RULE_RE = re.compile(
    r"\bRule\s+(\d+[A-Z]?(?:\.\d+)*)(?:\((\d+)\))?",
    re.IGNORECASE,
)
INTERNAL_REGULATION_RE = re.compile(
    r"\bRegulation\s+(\d+(?:\.\d+)*)(?:\((\d+)\))?",
    re.IGNORECASE,
)
INTERNAL_SCHEDULE_RE = re.compile(
    r"\bSchedule\s+(\d+)",
    re.IGNORECASE,
)
INTERNAL_PART_RE = re.compile(
    r"\bPart\s+(\d+)",
    re.IGNORECASE,
)
INTERNAL_APPENDIX_RE = re.compile(
    r"\b(?:Appendix|Annex)\s+(\d+)",
    re.IGNORECASE,
)
INTERNAL_CHAPTER_RE = re.compile(
    r"\bChapter\s+(\d+)",
    re.IGNORECASE,
)

# External law references: "DIFC Law No. X of YYYY" or full named laws
DIFC_LAW_NO_RE = re.compile(
    r"(?:DIFC\s+)?(?:[\w\s]+?\s+)?Law\s+No\.?\s*(\d+)\s+of\s+(\d{4})",
    re.IGNORECASE,
)
NAMED_LAW_RE = re.compile(
    r"(?:the\s+)?(?:DIFC\s+)?((?:[A-Z][a-z]+\s+){1,5})(?:Law|Regulations?|Rules?)(?:\s+\d{4})?",
)

# Case references
CASE_REF_RE = re.compile(
    r"\b(CFI|SCT|CA|ARB|ENF|DEC|TCD|ACT)[\s\-/]*(\d{1,4})\s*(?:/|\-|\s+of\s+)(\d{4})",
    re.IGNORECASE,
)

# RDC references
RDC_REF_RE = re.compile(
    r"\bRDC\s+(?:Part\s+)?(\d+[\.\d]*)",
    re.IGNORECASE,
)

# Consultation Paper references
CP_REF_RE = re.compile(
    r"Consultation\s+Paper\s+(?:No\.?\s*)?(\d+)(?:\s+of\s+(\d{4}))?",
    re.IGNORECASE,
)


def _load_json(path: Path) -> dict:
    """Load JSON file if it exists, else return empty dict."""
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _get_page_text(doc_path: Path, page_num: int) -> str:
    """Get text for a specific page from docling markdown or PyMuPDF."""
    doc_id = doc_path.stem
    DOCLING_DIR / f"{doc_id}.md"
    # For cross-reference extraction, PyMuPDF text is fine
    doc = pymupdf.open(str(doc_path))
    if page_num < len(doc):
        text = doc[page_num].get_text()
    else:
        text = ""
    doc.close()
    return text


def _get_all_pages_text(doc_path: Path) -> list[str]:
    """Get text for all pages of a document."""
    doc = pymupdf.open(str(doc_path))
    pages = [doc[i].get_text() for i in range(len(doc))]
    doc.close()
    return pages


def _normalize_case_id(prefix: str, number: str, year: str) -> str:
    """Normalize case ID to standard format like 'CFI 043/2020'."""
    return f"{prefix.upper()} {number.zfill(3)}/{year}"


def _resolve_law_name(context: str, law_name_index: dict) -> str | None:
    """Try to resolve a law name reference to a doc_id using law_name_index."""
    if not law_name_index:
        return None
    context_lower = context.lower().strip()
    # Direct lookup
    if context_lower in law_name_index:
        return law_name_index[context_lower]
    # Try partial match
    for key, doc_id in law_name_index.items():
        if key == "_meta":
            continue
        if key in context_lower or context_lower in key:
            return doc_id
    return None


def _resolve_article_page(doc_id: str, article_key: str, article_page_index: dict) -> int | None:
    """Try to resolve an article reference to a page number."""
    if not article_page_index or doc_id not in article_page_index:
        return None
    doc_articles = article_page_index[doc_id]
    if isinstance(doc_articles, dict) and article_key in doc_articles:
        val = doc_articles[article_key]
        if isinstance(val, int):
            return val
        if isinstance(val, list) and val:
            return val[0]
    return None


def extract_references(
    text: str,
    page_num: int,
    doc_id: str,
    law_name_index: dict,
    article_page_index: dict,
) -> list[dict]:
    """Extract all cross-references from a page of text."""
    refs = []

    # --- Internal article references ---
    for m in INTERNAL_ARTICLE_RE.finditer(text):
        art_num = m.group(1)
        sub_num = m.group(2)
        article_key = f"article_{art_num}"
        if sub_num:
            article_key = f"article_{art_num}_sub_{sub_num}"
        target_page = _resolve_article_page(doc_id, article_key, article_page_index)
        # Only record if it refers to a different page (cross-ref, not self-def)
        if target_page is not None and target_page != page_num + 1:
            refs.append(
                {
                    "target_doc": doc_id,
                    "target_page": target_page,
                    "type": "internal_article",
                    "context": m.group(0).strip(),
                },
            )

    # --- Internal schedule references ---
    for m in INTERNAL_SCHEDULE_RE.finditer(text):
        sched_num = m.group(1)
        article_key = f"schedule_{sched_num}"
        target_page = _resolve_article_page(doc_id, article_key, article_page_index)
        if target_page is not None and target_page != page_num + 1:
            refs.append(
                {
                    "target_doc": doc_id,
                    "target_page": target_page,
                    "type": "internal_schedule",
                    "context": m.group(0).strip(),
                },
            )

    # --- Internal part references ---
    for m in INTERNAL_PART_RE.finditer(text):
        part_num = m.group(1)
        article_key = f"part_{part_num}"
        target_page = _resolve_article_page(doc_id, article_key, article_page_index)
        if target_page is not None and target_page != page_num + 1:
            refs.append(
                {
                    "target_doc": doc_id,
                    "target_page": target_page,
                    "type": "internal_part",
                    "context": m.group(0).strip(),
                },
            )

    # --- Internal appendix references ---
    for m in INTERNAL_APPENDIX_RE.finditer(text):
        app_num = m.group(1)
        article_key = f"appendix_{app_num}"
        target_page = _resolve_article_page(doc_id, article_key, article_page_index)
        if target_page is not None and target_page != page_num + 1:
            refs.append(
                {
                    "target_doc": doc_id,
                    "target_page": target_page,
                    "type": "internal_appendix",
                    "context": m.group(0).strip(),
                },
            )

    # --- External law references (DIFC Law No. X of YYYY) ---
    for m in DIFC_LAW_NO_RE.finditer(text):
        context_str = m.group(0).strip()
        target_doc = _resolve_law_name(context_str, law_name_index)
        if target_doc and target_doc != doc_id:
            refs.append(
                {
                    "target_doc": target_doc,
                    "target_page": None,
                    "type": "external_law",
                    "context": context_str,
                },
            )

    # --- Named law references ---
    for m in NAMED_LAW_RE.finditer(text):
        context_str = m.group(0).strip()
        target_doc = _resolve_law_name(context_str, law_name_index)
        if target_doc and target_doc != doc_id:
            refs.append(
                {
                    "target_doc": target_doc,
                    "target_page": None,
                    "type": "external_law",
                    "context": context_str,
                },
            )

    # --- Case references ---
    for m in CASE_REF_RE.finditer(text):
        prefix, number, year = m.group(1), m.group(2), m.group(3)
        case_id = _normalize_case_id(prefix, number, year)
        refs.append(
            {
                "target_doc": None,  # Would need case_metadata_index to resolve
                "target_page": None,
                "type": "case_ref",
                "context": case_id,
            },
        )

    # --- RDC references ---
    for m in RDC_REF_RE.finditer(text):
        rule_num = m.group(1)
        refs.append(
            {
                "target_doc": None,
                "target_page": None,
                "type": "rdc_rule",
                "context": f"RDC {rule_num}",
            },
        )

    # --- Consultation Paper references ---
    for m in CP_REF_RE.finditer(text):
        cp_num = m.group(1)
        cp_year = m.group(2)
        context_str = f"Consultation Paper No. {cp_num}"
        if cp_year:
            context_str += f" of {cp_year}"
        refs.append(
            {
                "target_doc": None,
                "target_page": None,
                "type": "consultation_paper",
                "context": context_str,
            },
        )

    return refs


def _deduplicate_refs(refs: list[dict]) -> list[dict]:
    """Remove duplicate references on the same page."""
    seen = set()
    deduped = []
    for ref in refs:
        key = (ref["target_doc"], ref["target_page"], ref["type"], ref["context"])
        if key not in seen:
            seen.add(key)
            deduped.append(ref)
    return deduped


def extract_bridge_entities(graph: dict) -> dict[str, list[str]]:
    """Find entities (case IDs, law names, RDC rules) referenced from 2+ documents."""
    entity_docs: dict[str, set[str]] = defaultdict(set)

    for doc_id, pages in graph.items():
        for page_str, refs in pages.items():
            for ref in refs:
                ref_type = ref["type"]
                context = ref["context"]
                if ref_type in ("case_ref", "rdc_rule", "consultation_paper", "external_law"):
                    entity_docs[context].add(doc_id)

    # Only keep entities appearing in 2+ documents
    bridge = {}
    for entity, docs in entity_docs.items():
        if len(docs) >= 2:
            bridge[entity] = sorted(docs)

    return bridge


def build_graph():
    """Scan all documents and build the cross-reference graph."""
    law_name_index = _load_json(LAW_NAME_INDEX_PATH)
    article_page_index = _load_json(ARTICLE_PAGE_INDEX_PATH)

    if law_name_index:
        print(f"Loaded law_name_index: {len([k for k in law_name_index if k != '_meta'])} entries")
    else:
        print("Warning: law_name_index.json not found, external law resolution disabled")

    if article_page_index:
        print(f"Loaded article_page_index: {len(article_page_index)} documents")
    else:
        print("Warning: article_page_index.json not found, internal article page resolution disabled")

    pdf_files = sorted(DOCS_DIR.glob("*.pdf"))
    print(f"Scanning {len(pdf_files)} documents...")

    graph: dict[str, dict[str, list[dict]]] = {}
    total_refs = 0
    docs_with_refs = 0

    for i, pdf_path in enumerate(pdf_files):
        doc_id = pdf_path.stem
        pages_text = _get_all_pages_text(pdf_path)
        doc_refs: dict[str, list[dict]] = {}

        for page_num, text in enumerate(pages_text):
            if not text.strip():
                continue
            refs = extract_references(text, page_num, doc_id, law_name_index, article_page_index)
            refs = _deduplicate_refs(refs)
            if refs:
                doc_refs[str(page_num + 1)] = refs  # 1-indexed pages
                total_refs += len(refs)

        if doc_refs:
            graph[doc_id] = doc_refs
            docs_with_refs += 1

        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(pdf_files)} documents...")

    print(f"\nExtracted {total_refs} references from {docs_with_refs}/{len(pdf_files)} documents")

    # Extract bridge entities
    bridge_entities = extract_bridge_entities(graph)
    print(f"Found {len(bridge_entities)} bridge entities (appearing in 2+ documents)")

    # Add bridge entities under special key
    output = dict(graph)
    output["_bridge_entities"] = bridge_entities

    # Write output
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote cross-reference graph to {OUTPUT}")
    return output


if __name__ == "__main__":
    build_graph()
