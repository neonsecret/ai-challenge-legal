"""
fix_router_doc_ids.py

Rebuilds router index files to use name-based pgvector pdf_ids
instead of SHA-256 hex hashes.

Strategy:
1. Collect all unique SHA hashes from all index files.
2. For each SHA, try to match against pgvector pdf_ids:
   a. For law SHAs: use law_name_index canonical names as query hints.
   b. For case SHAs: use case_metadata_index case IDs for pattern matching.
   c. Fallback: extract first-page text from PDF using pymupdf and infer.
3. Build sha -> [pdf_id, ...] mapping, save to data/sha_to_pdf_ids.json.
4. Update all index files in-place (save *.json.bak first).
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data"
DOCS_DIR = DATA_DIR / "documents"

SHA_RE = re.compile(r"^[0-9a-f]{63,64}$")  # SHA-256 is 64 hex chars


def is_sha(value: str) -> bool:
    """Return True if value looks like a SHA-256 hex hash (64 hex chars)."""
    return bool(SHA_RE.match(str(value)))


def get_db_engine():
    """Create a synchronous SQLAlchemy engine from DATABASE_URL."""
    db_url = os.environ["DATABASE_URL"]
    sync_url = db_url.replace("+asyncpg", "").replace("+aiosqlite", "")
    return create_engine(sync_url)


def load_all_difc_pdf_ids(engine) -> list[str]:
    """Load every distinct pdf_id in the difc corpus."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT pdf_id FROM chunks WHERE corpus='difc' ORDER BY pdf_id")
        ).fetchall()
    return [r[0] for r in rows]


def query_pdf_ids_by_source_like(engine, pattern: str) -> list[str]:
    """Return distinct pdf_ids whose source_file matches a LIKE pattern (difc corpus)."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT DISTINCT pdf_id FROM chunks "
                "WHERE corpus='difc' AND LOWER(source_file) LIKE :pat "
                "ORDER BY pdf_id LIMIT 20"
            ),
            {"pat": pattern},
        ).fetchall()
    return [r[0] for r in rows]


def query_pdf_ids_by_id_like(engine, pattern: str) -> list[str]:
    """Return distinct pdf_ids whose pdf_id matches a LIKE pattern (difc corpus)."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT DISTINCT pdf_id FROM chunks "
                "WHERE corpus='difc' AND LOWER(pdf_id) LIKE :pat "
                "ORDER BY pdf_id LIMIT 20"
            ),
            {"pat": pattern},
        ).fetchall()
    return [r[0] for r in rows]


def law_name_to_pgvector_search_terms(canonical_name: str) -> list[str]:
    """
    Convert a canonical law name like 'Contract Law' to lowercase keyword(s)
    for LIKE queries against pdf_id column.

    Returns ordered list of patterns to try (most specific first).
    """
    name_lower = canonical_name.lower().strip()
    # Remove trailing "law", "regulations", "order" for the prefix keyword
    # e.g. "Contract Law" -> "contract_law"
    # e.g. "Employment Regulations" -> "employment_regulation"
    slug = re.sub(r"\s+", "_", name_lower)
    return [f"%{slug}%", f"%{slug.replace('_law', '')}%_law%"]


def extract_first_page_text(pdf_path: Path) -> str:
    """Extract text from first page of a PDF using pymupdf (fitz)."""
    try:
        import fitz  # type: ignore[import]

        doc = fitz.open(str(pdf_path))
        if doc.page_count == 0:
            return ""
        text = doc[0].get_text()
        doc.close()
        return text
    except Exception as exc:
        logger.warning("pymupdf failed for %s: %s", pdf_path.name, exc)
        return ""


def normalize_case_id_to_like(case_id: str) -> str:
    """
    Convert a case_id like 'CFI 047/2020' to a LIKE pattern 'cfi%047%2020'.
    Handles SCT/CFI/CA/ARB prefixes with spaces, slashes, or dashes.
    """
    # Extract prefix, number, year with a regex
    m = re.match(
        r"^(CFI|SCT|CA|ARB|ENF|DEC|TCD|ACT)[\s\-/]+(\d+)[\s\-/]+(\d{4})$",
        case_id.strip(),
        re.IGNORECASE,
    )
    if m:
        prefix, number, year = m.group(1).lower(), m.group(2).zfill(3), m.group(3)
        return f"{prefix}%{number}%{year}%"
    # Fallback: just replace non-alphanumeric chars with %
    fallback = re.sub(r"[^a-z0-9]+", "%", case_id.lower())
    return f"%{fallback}%"


def court_order_key_to_pgvector_pattern(key: str) -> str | None:
    """
    Convert a court_order_index key like 'sct_order_1_of_2023' or
    'rules_of_court_order_4_of_2017' to a LIKE pattern for pgvector pdf_id.

    Examples:
        court_order_1_of_2023  → 'difc-courts-order%1%2023%'
        sct_order_1_of_2023    → 'difc-courts-order%1%2023%'
        rules_of_court_order_4_of_2017 → 'difc-courts-rules-court-order%4%2017%'
        dra_order_1_of_2016    → 'dra-order%1%2016%'
    """
    m = re.match(
        r"^(dra|rules_of_court|sct|court)_order_(\d+)_of_(\d+)$", key
    )
    if not m:
        return None
    order_type, num, year = m.group(1), m.group(2), m.group(3)
    if order_type == "dra":
        return f"dra%order%{num}%{year}%"
    if order_type == "rules_of_court":
        return f"difc-courts-rules%order%{num}%{year}%"
    # sct and court both map to difc-courts-order-no-X-YYYY
    return f"difc-courts-order%{num}%{year}%"


def build_sha_to_pdf_ids_mapping(
    engine,
    all_shas: set[str],
    law_name_index: dict,
    case_metadata_index: dict,
    court_order_index: dict,
    all_pgvector_ids: list[str],
) -> dict[str, list[str]]:
    """
    Build a comprehensive sha -> [pdf_id, ...] mapping.

    Priority order per SHA:
    1. law_name_index canonical_names lookup → use law name to query pgvector
    2. case_metadata_index → use case_id to query pgvector
    3. court_order_index key patterns → infer DIFC court order pdf_ids
    4. PDF first-page text fallback (if PDF exists on disk)
    """
    mapping: dict[str, list[str]] = {}

    # Build reverse: sha -> canonical law name from law_name_index._meta.canonical_names
    meta = law_name_index.get("_meta", {})
    canonical_names: dict[str, str] = meta.get("canonical_names", {})
    sha_to_canonical: dict[str, str] = {sha: name for sha, name in canonical_names.items()}

    # Build reverse: sha -> [case_id, ...] from case_metadata_index
    sha_to_case_ids: dict[str, list[str]] = {}
    for case_id, case_data in case_metadata_index.items():
        for doc in case_data.get("docs", []):
            doc_id = doc.get("doc_id", "")
            if is_sha(doc_id):
                sha_to_case_ids.setdefault(doc_id, []).append(case_id)

    # Build reverse: sha -> [court_order_key, ...] from court_order_index
    sha_to_court_order_keys: dict[str, list[str]] = {}
    for key, val in court_order_index.items():
        if isinstance(val, str) and is_sha(val):
            sha_to_court_order_keys.setdefault(val, []).append(key)

    # Also collect all SHA values from law_name_index (non-_meta string values)
    sha_to_law_variants: dict[str, list[str]] = {}
    for key, val in law_name_index.items():
        if key == "_meta":
            continue
        if isinstance(val, str) and is_sha(val):
            sha_to_law_variants.setdefault(val, []).append(key)

    logger.info(
        "SHA inventory: %d total, %d have canonical law name, %d have case IDs, %d have law variants, %d have court order keys",
        len(all_shas),
        len([s for s in all_shas if s in sha_to_canonical]),
        len([s for s in all_shas if s in sha_to_case_ids]),
        len([s for s in all_shas if s in sha_to_law_variants]),
        len([s for s in all_shas if s in sha_to_court_order_keys]),
    )

    for sha in sorted(all_shas):
        pdf_ids: list[str] = []

        # --- Method 1: canonical law name lookup ---
        if sha in sha_to_canonical:
            canon = sha_to_canonical[sha]
            patterns = law_name_to_pgvector_search_terms(canon)
            for pat in patterns:
                results = query_pdf_ids_by_id_like(engine, pat)
                # Filter to only actual law-type pdf_ids (underscore-slug format)
                law_results = [r for r in results if re.match(r"^[a-z0-9_]+$", r)]
                if law_results:
                    pdf_ids = law_results
                    break
            if pdf_ids:
                logger.info("  [law-canonical] SHA %s → %s (%s)", sha[:12], pdf_ids, canon)

        # --- Method 2: law name variants from law_name_index ---
        if not pdf_ids and sha in sha_to_law_variants:
            variants = sha_to_law_variants[sha]
            for variant in variants:
                # Use the variant as a keyword query
                slug = re.sub(r"\s+", "_", variant.lower().strip())
                slug = re.sub(r"[^a-z0-9_]", "_", slug)
                results = query_pdf_ids_by_id_like(engine, f"%{slug}%")
                law_results = [r for r in results if re.match(r"^[a-z0-9_]+$", r)]
                if law_results:
                    pdf_ids = law_results
                    logger.info(
                        "  [law-variant] SHA %s → %s (via variant '%s')",
                        sha[:12],
                        pdf_ids,
                        variant,
                    )
                    break

        # --- Method 3: case ID lookup ---
        if not pdf_ids and sha in sha_to_case_ids:
            case_ids = sha_to_case_ids[sha]
            for case_id in case_ids:
                pat = normalize_case_id_to_like(case_id)
                results = query_pdf_ids_by_id_like(engine, pat)
                if results:
                    pdf_ids.extend(results)
            # Deduplicate while preserving order
            seen: set[str] = set()
            unique: list[str] = []
            for pid in pdf_ids:
                if pid not in seen:
                    seen.add(pid)
                    unique.append(pid)
            pdf_ids = unique
            if pdf_ids:
                logger.info(
                    "  [case] SHA %s → %d match(es) for case(s) %s",
                    sha[:12],
                    len(pdf_ids),
                    case_ids,
                )

        # --- Method 3.5: court order key pattern matching ---
        if not pdf_ids and sha in sha_to_court_order_keys:
            co_keys = sha_to_court_order_keys[sha]
            for co_key in co_keys:
                pat = court_order_key_to_pgvector_pattern(co_key)
                if pat:
                    results = query_pdf_ids_by_id_like(engine, pat)
                    if results:
                        pdf_ids = results[:1]  # take most specific match
                        logger.info(
                            "  [court-order] SHA %s → %s (key=%s)",
                            sha[:12],
                            pdf_ids,
                            co_key,
                        )
                        break

        # --- Method 4: PDF first-page text fallback ---
        if not pdf_ids:
            pdf_path = DOCS_DIR / f"{sha}.pdf"
            if pdf_path.exists():
                text_content = extract_first_page_text(pdf_path)
                pdf_ids = _infer_from_text(engine, text_content, all_pgvector_ids)
                if pdf_ids:
                    logger.info(
                        "  [pdf-text] SHA %s → %s", sha[:12], pdf_ids
                    )

        if not pdf_ids:
            logger.warning("  [UNMAPPED] SHA %s (no pgvector match found)", sha[:12])

        mapping[sha] = pdf_ids

    return mapping


def _infer_from_text(
    engine,
    text_content: str,
    all_pgvector_ids: list[str],
) -> list[str]:
    """
    Try to infer pdf_id from extracted PDF text.
    Looks for law names and case IDs in first-page text.
    """
    if not text_content:
        return []

    # Try case ID pattern
    case_m = re.search(
        r"(CFI|SCT|CA|ARB|ENF)[\s\-/]*(\d+)\s*(?:/|-|\s+of\s+)(\d{4})",
        text_content,
        re.IGNORECASE,
    )
    if case_m:
        prefix, number, year = (
            case_m.group(1).lower(),
            case_m.group(2).zfill(3),
            case_m.group(3),
        )
        pat = f"{prefix}%{number}%{year}%"
        return query_pdf_ids_by_id_like(engine, pat)

    # Try law name keywords (simple approach: look for known law keywords)
    law_keywords = [
        ("contract law", "contract_law"),
        ("employment law", "employment_law"),
        ("companies law", "companies_law"),
        ("arbitration law", "arbitration_law"),
        ("data protection law", "data_protection_law"),
        ("insolvency law", "insolvency_law"),
        ("trust law", "trust_law"),
        ("foundations law", "foundations_law"),
        ("real property law", "real_property_law"),
        ("securities law", "securities_law"),
        ("intellectual property law", "intellectual_property_law"),
        ("operating law", "operating_law"),
        ("netting law", "netting_law"),
        ("strata title law", "strata_title_law"),
    ]
    lower_text = text_content.lower()
    for keyword, slug in law_keywords:
        if keyword in lower_text:
            return query_pdf_ids_by_id_like(engine, f"%{slug}%")

    return []


def collect_all_shas(*index_dicts) -> set[str]:
    """Recursively collect all SHA-like string values from nested dicts/lists."""
    shas: set[str] = set()

    def _walk(obj):
        if isinstance(obj, str):
            if is_sha(obj):
                shas.add(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    for d in index_dicts:
        _walk(d)
    return shas


def backup_file(path: Path) -> None:
    bak = path.with_suffix(".json.bak")
    shutil.copy2(path, bak)
    logger.info("Backed up %s → %s", path.name, bak.name)


def apply_mapping_law_name_index(
    data: dict, sha_map: dict[str, list[str]]
) -> tuple[dict, int, int]:
    """
    Replace SHA string values in law_name_index with the first matched pdf_id.
    _meta block is preserved as-is.
    """
    mapped = updated = skipped = 0
    new_data: dict = {}
    for key, val in data.items():
        if key == "_meta":
            # Update _meta.canonical_names and _meta.reliable_laws/_meta.unreliable_laws
            new_meta = dict(val)
            if "canonical_names" in new_meta:
                new_cn: dict = {}
                for sha, cname in new_meta["canonical_names"].items():
                    if is_sha(sha) and sha in sha_map and sha_map[sha]:
                        new_cn[sha_map[sha][0]] = cname
                        mapped += 1
                    else:
                        new_cn[sha] = cname
                        if is_sha(sha):
                            skipped += 1
                new_meta["canonical_names"] = new_cn
            if "reliable_laws" in new_meta:
                new_rl: list = []
                for sha in new_meta["reliable_laws"]:
                    if is_sha(sha) and sha in sha_map and sha_map[sha]:
                        new_rl.append(sha_map[sha][0])
                    else:
                        new_rl.append(sha)
                new_meta["reliable_laws"] = new_rl
            if "unreliable_laws" in new_meta:
                new_ul: dict = {}
                for sha, reason in new_meta["unreliable_laws"].items():
                    if is_sha(sha) and sha in sha_map and sha_map[sha]:
                        new_ul[sha_map[sha][0]] = reason
                    else:
                        new_ul[sha] = reason
                new_ul_mapped = {
                    (sha_map[sha][0] if is_sha(sha) and sha in sha_map and sha_map[sha] else sha): reason
                    for sha, reason in new_meta["unreliable_laws"].items()
                }
                new_meta["unreliable_laws"] = new_ul_mapped
            new_data[key] = new_meta
            continue

        if isinstance(val, str) and is_sha(val):
            if val in sha_map and sha_map[val]:
                new_data[key] = sha_map[val][0]
                updated += 1
            else:
                new_data[key] = val  # keep SHA as-is
                skipped += 1
        else:
            new_data[key] = val

    return new_data, updated, skipped


def apply_mapping_case_metadata_index(
    data: dict, sha_map: dict[str, list[str]]
) -> tuple[dict, int, int]:
    """
    Replace doc_id SHA in case_metadata_index docs with first matched pdf_id.
    Multiple pgvector matches: keep only the first one (most specific).
    """
    updated = skipped = 0
    new_data: dict = {}
    for case_id, case_data in data.items():
        new_case = dict(case_data)
        new_docs = []
        for doc in case_data.get("docs", []):
            new_doc = dict(doc)
            doc_id = new_doc.get("doc_id", "")
            if is_sha(doc_id):
                if doc_id in sha_map and sha_map[doc_id]:
                    # Pick the best match: prefer the one closest in length to case_id hint
                    # For multiple matches (one case has many documents), keep first
                    new_doc["doc_id"] = sha_map[doc_id][0]
                    updated += 1
                else:
                    skipped += 1
            new_docs.append(new_doc)
        new_case["docs"] = new_docs
        new_data[case_id] = new_case
    return new_data, updated, skipped


def apply_mapping_article_page_index(
    data: dict, sha_map: dict[str, list[str]]
) -> tuple[dict, int, int]:
    """
    Replace outer SHA keys in article_page_index with mapped pdf_ids.
    If multiple SHA keys map to the same pdf_id, last one wins (log a warning).
    """
    updated = skipped = 0
    new_data: dict = {}
    for sha_key, val in data.items():
        if is_sha(sha_key):
            if sha_key in sha_map and sha_map[sha_key]:
                new_key = sha_map[sha_key][0]
                if new_key in new_data:
                    logger.warning(
                        "article_page_index: collision — two SHAs map to same pdf_id '%s'", new_key
                    )
                new_data[new_key] = val
                updated += 1
            else:
                new_data[sha_key] = val  # keep SHA as-is
                skipped += 1
        else:
            new_data[sha_key] = val
    return new_data, updated, skipped


def apply_mapping_generic_string_values(
    data: dict, sha_map: dict[str, list[str]], file_label: str
) -> tuple[dict, int, int]:
    """
    Generic: replace SHA string values (not keys) in a flat dict.
    Used for latest_edition_index, appeal_index, court_order_index.
    """
    updated = skipped = 0
    new_data: dict = {}
    for key, val in data.items():
        if isinstance(val, str) and is_sha(val):
            if val in sha_map and sha_map[val]:
                new_data[key] = sha_map[val][0]
                updated += 1
            else:
                new_data[key] = val
                skipped += 1
        elif isinstance(val, dict):
            # latest_edition_index has nested dicts with doc_id key
            new_val = dict(val)
            doc_id = new_val.get("doc_id", "")
            if isinstance(doc_id, str) and is_sha(doc_id):
                if doc_id in sha_map and sha_map[doc_id]:
                    new_val["doc_id"] = sha_map[doc_id][0]
                    updated += 1
                else:
                    skipped += 1
            new_data[key] = new_val
        else:
            new_data[key] = val
    return new_data, updated, skipped


def main():
    engine = get_db_engine()
    logger.info("Connected to database.")

    # Load index files
    with open(DATA_DIR / "law_name_index.json") as f:
        law_name_index = json.load(f)
    with open(DATA_DIR / "case_metadata_index.json") as f:
        case_metadata_index = json.load(f)
    with open(DATA_DIR / "article_page_index.json") as f:
        article_page_index = json.load(f)
    with open(DATA_DIR / "latest_edition_index.json") as f:
        latest_edition_index = json.load(f)
    with open(DATA_DIR / "appeal_index.json") as f:
        appeal_index = json.load(f)
    with open(DATA_DIR / "court_order_index.json") as f:
        court_order_index = json.load(f)

    # Collect all unique SHAs across all index files
    all_shas = collect_all_shas(
        law_name_index,
        case_metadata_index,
        article_page_index,
        latest_edition_index,
        appeal_index,
        court_order_index,
    )
    logger.info("Found %d unique SHAs across all index files.", len(all_shas))

    # Load all pgvector pdf_ids for DIFC corpus
    all_pgvector_ids = load_all_difc_pdf_ids(engine)
    logger.info("Loaded %d distinct DIFC pdf_ids from pgvector.", len(all_pgvector_ids))

    # Build sha -> [pdf_id] mapping
    sha_map = build_sha_to_pdf_ids_mapping(
        engine,
        all_shas,
        law_name_index,
        case_metadata_index,
        court_order_index,
        all_pgvector_ids,
    )

    # Stats
    mapped_count = sum(1 for v in sha_map.values() if v)
    unmapped_count = sum(1 for v in sha_map.values() if not v)
    logger.info(
        "Mapping result: %d mapped, %d unmapped (out of %d total SHAs).",
        mapped_count,
        unmapped_count,
        len(sha_map),
    )

    # Save mapping for debugging
    mapping_path = DATA_DIR / "sha_to_pdf_ids.json"
    with open(mapping_path, "w") as f:
        json.dump(sha_map, f, indent=2)
    logger.info("Saved SHA mapping to %s", mapping_path)

    # Print unmapped SHAs
    unmapped = [sha for sha, v in sha_map.items() if not v]
    if unmapped:
        logger.warning("Unmapped SHAs (%d):", len(unmapped))
        for sha in sorted(unmapped)[:30]:
            logger.warning("  %s", sha)
        if len(unmapped) > 30:
            logger.warning("  ... and %d more", len(unmapped) - 30)

    # --- Apply mapping to each index file ---

    # 1. law_name_index.json
    path = DATA_DIR / "law_name_index.json"
    backup_file(path)
    new_law_name_index, u, s = apply_mapping_law_name_index(law_name_index, sha_map)
    with open(path, "w") as f:
        json.dump(new_law_name_index, f, indent=2)
    logger.info("law_name_index.json: %d updated, %d kept as SHA", u, s)

    # 2. case_metadata_index.json
    path = DATA_DIR / "case_metadata_index.json"
    backup_file(path)
    new_case_index, u, s = apply_mapping_case_metadata_index(case_metadata_index, sha_map)
    with open(path, "w") as f:
        json.dump(new_case_index, f, indent=2)
    logger.info("case_metadata_index.json: %d updated, %d kept as SHA", u, s)

    # 3. article_page_index.json
    path = DATA_DIR / "article_page_index.json"
    backup_file(path)
    new_article_index, u, s = apply_mapping_article_page_index(article_page_index, sha_map)
    with open(path, "w") as f:
        json.dump(new_article_index, f, indent=2)
    logger.info("article_page_index.json: %d updated, %d kept as SHA", u, s)

    # 4. latest_edition_index.json
    path = DATA_DIR / "latest_edition_index.json"
    backup_file(path)
    new_latest, u, s = apply_mapping_generic_string_values(
        latest_edition_index, sha_map, "latest_edition_index"
    )
    with open(path, "w") as f:
        json.dump(new_latest, f, indent=2)
    logger.info("latest_edition_index.json: %d updated, %d kept as SHA", u, s)

    # 5. appeal_index.json — values are dicts (no doc_id), so no SHA replacement needed
    # but check anyway for forward-compatibility
    path = DATA_DIR / "appeal_index.json"
    backup_file(path)
    new_appeal, u, s = apply_mapping_generic_string_values(
        appeal_index, sha_map, "appeal_index"
    )
    with open(path, "w") as f:
        json.dump(new_appeal, f, indent=2)
    logger.info("appeal_index.json: %d updated, %d kept as SHA", u, s)

    # 6. court_order_index.json
    path = DATA_DIR / "court_order_index.json"
    backup_file(path)
    new_court_order, u, s = apply_mapping_generic_string_values(
        court_order_index, sha_map, "court_order_index"
    )
    with open(path, "w") as f:
        json.dump(new_court_order, f, indent=2)
    logger.info("court_order_index.json: %d updated, %d kept as SHA", u, s)

    logger.info("All index files updated successfully.")

    # --- Verification spot-check ---
    with open(DATA_DIR / "law_name_index.json") as f:
        verify_law = json.load(f)
    contract_law_val = verify_law.get("contract law", "(missing)")
    employment_law_val = verify_law.get("employment law", "(missing)")
    logger.info("Verification — law_name_index['contract law'] = %s", contract_law_val)
    logger.info("Verification — law_name_index['employment law'] = %s", employment_law_val)


if __name__ == "__main__":
    main()
