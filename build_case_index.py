#!/usr/bin/env python3
"""
Build case_metadata_index.json by scanning all CASE documents.
For each case document, extracts:
  - Case ID (from filename or first page)
  - Judge name(s) + page where found
  - Date of issue + page
  - Parties (claimant, defendant) + page
  - Claim value (if monetary) + page
  - Outcome/order + page (usually last substantive page)

Uses Claude Haiku to extract structured data from first 3 pages + last 3 pages of each doc.
Saves to data/case_metadata_index.json.

Usage: uv run python build_case_index.py [--docs-dir data/documents]
"""
import anthropic, fitz, json, os, re, argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
DOCS_DIR = Path('data/documents')

EXTRACT_PROMPT = """Extract structured metadata from these legal document pages.

Pages:
{pages}

Extract as JSON (use null for missing fields):
{{
  "case_id": "e.g. CFI 123/2025",
  "case_type": "CFI|SCT|CA|ARB|ENF|DEC|TCD",
  "judge": {{"name": "...", "page": N}},
  "date_of_issue": {{"value": "YYYY-MM-DD", "page": N}},
  "claimant": {{"name": "...", "page": N}},
  "defendant": {{"name": "...", "page": N}},
  "claim_value_aed": {{"value": 12345.0, "page": N}},
  "outcome": {{"summary": "...", "page": N}}
}}

Only include fields that are clearly stated in the text. Page numbers are 1-indexed."""


def get_doc_pages(doc_path: Path, n_first=3, n_last=3) -> list[tuple[int, str]]:
    """Return (page_num, text) for first N and last N pages."""
    doc = fitz.open(str(doc_path))
    total = len(doc)
    pages = []
    indices = list(range(min(n_first, total)))
    if total > n_first:
        last_start = max(n_first, total - n_last)
        indices += list(range(last_start, total))
    for i in set(indices):
        pages.append((i + 1, doc[i].get_text()))
    return sorted(pages)


def extract_metadata(doc_id: str) -> dict | None:
    path = DOCS_DIR / f'{doc_id}.pdf'
    if not path.exists():
        return None
    pages = get_doc_pages(path)
    pages_text = '\n\n'.join(f'[Page {p}]\n{t[:1500]}' for p, t in pages)

    try:
        resp = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=1000,
            messages=[{'role': 'user', 'content': EXTRACT_PROMPT.format(pages=pages_text)}]
        )
        text = resp.content[0].text
        # Extract JSON
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception as e:
        print(f'  Error: {e}')
    return None


def build_index(docs_dir: Path = DOCS_DIR) -> dict:
    """Build index: {case_id: {docs: [{doc_id, metadata}]}}"""
    # Load article_page_index to identify CASE docs
    art_idx = json.load(open('data/article_page_index.json'))
    case_docs = {k: v for k, v in art_idx.items() if v.get('type') == 'CASE'}

    # Group by case_id
    by_case: dict[str, list] = {}
    for doc_id, info in case_docs.items():
        print(f'Processing {doc_id[:16]}...')
        meta = extract_metadata(doc_id)
        if meta and meta.get('case_id'):
            cid = meta['case_id'].strip()
            if cid not in by_case:
                by_case[cid] = {'docs': []}
            by_case[cid]['docs'].append({'doc_id': doc_id, 'metadata': meta})
            print(f'  {cid}: {doc_id[:16]}...')
        else:
            print(f'  [no case_id] {doc_id[:16]}...')

    return by_case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--docs-dir', default='data/documents')
    args = parser.parse_args()

    print('Building case metadata index...')
    idx = build_index(Path(args.docs_dir))

    out = 'data/case_metadata_index.json'
    with open(out, 'w') as f:
        json.dump(idx, f, indent=2)
    print(f'Saved {len(idx)} cases to {out}')


if __name__ == '__main__':
    main()
