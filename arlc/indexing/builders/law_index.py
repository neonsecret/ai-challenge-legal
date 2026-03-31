#!/usr/bin/env python3
"""
Build/update law indexes:
1. Runs build_article_index.py logic on new documents
2. Builds latest_edition_index.json: {law_name → {doc_id, year}} — always the newest edition
3. Updates law_name_index.json with new law name variants

Usage: uv run python build_law_index_v2.py [--docs-dir data/documents]
"""
import argparse
import json
import os
import re
from pathlib import Path

import anthropic
import fitz
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
DOCS_DIR = Path('data/documents')


def get_law_name_and_year(doc_id: str) -> tuple[str, int] | None:
    """Extract law name and year from first page of a LAW document."""
    path = DOCS_DIR / f'{doc_id}.pdf'
    if not path.exists():
        return None
    doc = fitz.open(str(path))
    first_page = doc[0].get_text()[:2000]

    # Try regex first (fast, free)
    year_match = re.search(r'\b(20\d{2}|19\d{2})\b', first_page)
    year = int(year_match.group()) if year_match else 0

    # Extract law name via Haiku
    resp = client.messages.create(
        model='claude-haiku-4-5',
        max_tokens=100,
        messages=[{
            'role': 'user',
            'content': f'What is the official name of this DIFC law? Reply with ONLY the name (e.g. "Employment Law").\n\n{first_page[:500]}'
        }]
    )
    name = resp.content[0].text.strip()
    return (name, year) if name else None


def build_edition_index() -> dict:
    """Build latest_edition_index.json."""
    art_idx = json.load(open('data/article_page_index.json'))
    law_docs = {k: v for k, v in art_idx.items() if v.get('type') == 'LAW'}

    # Group by law name, keep latest year
    editions: dict[str, dict] = {}
    for doc_id in law_docs:
        print(f'Processing {doc_id[:16]}...')
        result = get_law_name_and_year(doc_id)
        if result:
            name, year = result
            name_lower = name.lower().strip()
            if name_lower not in editions or year > editions[name_lower]['year']:
                editions[name_lower] = {'doc_id': doc_id, 'year': year, 'name': name}
            print(f'  {name} ({year}): {doc_id[:16]}...')

    with open('data/latest_edition_index.json', 'w') as f:
        json.dump(editions, f, indent=2)
    print(f'Saved {len(editions)} law editions')
    return editions


def update_law_name_index(editions: dict):
    """Update law_name_index.json with new editions."""
    try:
        idx = json.load(open('data/law_name_index.json'))
    except FileNotFoundError:
        idx = {}

    for name_lower, entry in editions.items():
        doc_id = entry['doc_id']
        entry['name']
        # Add multiple variants
        variants = [
            name_lower,
            re.sub(r'\s+\d{4}$', '', name_lower),  # without year
            re.sub(r'^difc\s+', '', name_lower),  # without DIFC prefix
            re.sub(r'\s+law$', '', name_lower),  # without "law" suffix
        ]
        for v in variants:
            if v and len(v) > 3:
                idx[v] = doc_id

    with open('data/law_name_index.json', 'w') as f:
        json.dump(idx, f, indent=2)
    print(f'law_name_index has {len(idx)} entries')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--docs-dir', default='data/documents')
    parser.parse_args()

    print('Building law edition index...')
    editions = build_edition_index()
    update_law_name_index(editions)


if __name__ == '__main__':
    main()
