#!/usr/bin/env python3
"""Generate bridging facts from cross-reference graph and AKU index.

# Bridging fact generation from IndexRAG (Bao & Shi, 2026, arXiv:2603.16415)

Bridging facts encode cross-document reasoning by merging information about
entities that appear in multiple documents.

Two modes:
  --no-llm (default): deterministic — concatenate relevant text snippets
  --llm: use Haiku to generate natural-language bridging facts

Usage:
    python build_bridging_facts.py                     # deterministic mode
    python build_bridging_facts.py --llm               # LLM mode (uses Haiku)
    python build_bridging_facts.py --max-entities 10   # limit entity count
"""

import argparse
import json
import re
import sys
from pathlib import Path

GRAPH_PATH = Path("data/cross_reference_graph.json")
AKU_PATH = Path("data/aku_index.json")
OUTPUT_PATH = Path("data/bridging_facts.json")
DOCUMENTS_DIR = Path("data/documents")

# Maximum snippet length per doc per entity (chars)
MAX_SNIPPET_CHARS = 600


def load_graph() -> dict:
    with open(GRAPH_PATH) as f:
        return json.load(f)


def load_aku_index() -> dict | None:
    if AKU_PATH.exists():
        with open(AKU_PATH) as f:
            return json.load(f)
    return None


def _get_page_text(doc_id: str, page_num: int) -> str:
    """Extract text from a specific page using PyMuPDF (0-based page_num)."""
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf
    pdf_path = DOCUMENTS_DIR / f"{doc_id}.pdf"
    if not pdf_path.exists():
        return ""
    doc = pymupdf.open(str(pdf_path))
    text = ""
    if page_num < len(doc):
        text = doc[page_num].get_text()
    doc.close()
    return text


def _find_entity_pages(entity: str, doc_id: str, graph: dict) -> list[int]:
    """Find which pages in a document mention a bridge entity (0-based)."""
    pages = []
    doc_refs = graph.get(doc_id, {})
    for page_str, refs in doc_refs.items():
        for ref in refs:
            if ref.get("context") and entity in ref["context"]:
                pages.append(int(page_str) - 1)  # graph uses 1-based
                break
    # Deduplicate and sort
    return sorted(set(pages))


def _extract_entity_sentences(text: str, entity: str) -> list[str]:
    """Extract sentences from text that mention the entity."""
    # Split into sentences (rough but good enough for legal text)
    sentences = re.split(r"(?<=[.;])\s+", text)
    matches = []
    entity_lower = entity.lower()
    for sent in sentences:
        if entity_lower in sent.lower() and len(sent.strip()) > 20:
            matches.append(sent.strip())
    return matches


def _get_aku_facts_for_entity(entity: str, doc_id: str, aku_index: dict) -> list[dict]:
    """Filter AKUs whose q or a contains the entity."""
    facts = []
    doc_akus = aku_index.get(doc_id, {})
    entity_lower = entity.lower()
    for page_str, page_akus in doc_akus.items():
        for aku in page_akus:
            q = aku.get("q", "")
            a = aku.get("a", "")
            if entity_lower in q.lower() or entity_lower in a.lower():
                facts.append({"page": int(page_str), "q": q, "a": a})
    return facts


def _build_snippet_from_akus(entity: str, doc_id: str, aku_facts: list[dict]) -> tuple[str, list[int]]:
    """Build a text snippet from AKU facts, return (snippet, pages)."""
    parts = []
    pages = set()
    for fact in aku_facts[:5]:  # limit per doc
        parts.append(f"Q: {fact['q']} A: {fact['a']}")
        pages.add(fact["page"])
    snippet = " | ".join(parts)
    if len(snippet) > MAX_SNIPPET_CHARS:
        snippet = snippet[:MAX_SNIPPET_CHARS] + "..."
    return snippet, sorted(pages)


def _build_snippet_from_pages(entity: str, doc_id: str, entity_pages: list[int], graph: dict) -> tuple[str, list[int]]:
    """Build a text snippet from raw page text, return (snippet, pages_used)."""
    all_sentences = []
    pages_used = set()
    for page_num in entity_pages[:3]:  # limit pages scanned
        text = _get_page_text(doc_id, page_num)
        if not text:
            continue
        sentences = _extract_entity_sentences(text, entity)
        if sentences:
            pages_used.add(page_num + 1)  # convert to 1-based for output
            all_sentences.extend(sentences[:3])  # limit sentences per page

    snippet = " ".join(all_sentences)
    if len(snippet) > MAX_SNIPPET_CHARS:
        snippet = snippet[:MAX_SNIPPET_CHARS] + "..."
    return snippet, sorted(pages_used)


def generate_bridging_facts_deterministic(bridge_entities: dict, graph: dict, aku_index: dict | None) -> list[dict]:
    """Generate bridging facts without LLM — concatenate relevant snippets."""
    facts = []
    for entity, doc_ids in bridge_entities.items():
        if len(doc_ids) < 2:
            continue

        doc_snippets = []
        source_pages = []

        for doc_id in doc_ids:
            snippet = ""
            pages = []

            # Try AKU index first
            if aku_index:
                aku_facts = _get_aku_facts_for_entity(entity, doc_id, aku_index)
                if aku_facts:
                    snippet, pages = _build_snippet_from_akus(entity, doc_id, aku_facts)

            # Fallback to raw page text
            if not snippet:
                entity_pages = _find_entity_pages(entity, doc_id, graph)
                if entity_pages:
                    snippet, pages = _build_snippet_from_pages(entity, doc_id, entity_pages, graph)

            if snippet:
                doc_snippets.append(f"[{doc_id[:16]}]: {snippet}")
                for p in pages:
                    source_pages.append({"doc_id": doc_id, "page": p})

        if len(doc_snippets) >= 2:
            combined = f"{entity} — " + " || ".join(doc_snippets)
            facts.append(
                {
                    "fact": combined,
                    "source_docs": doc_ids,
                    "source_pages": source_pages,
                    "bridge_entity": entity,
                }
            )

    return facts


def generate_bridging_facts_llm(bridge_entities: dict, graph: dict, aku_index: dict | None) -> list[dict]:
    """Generate bridging facts using Haiku for natural language synthesis."""
    import anthropic

    client = anthropic.Anthropic()
    facts = []

    for entity, doc_ids in bridge_entities.items():
        if len(doc_ids) < 2:
            continue

        doc_snippets = []
        source_pages = []

        for doc_id in doc_ids:
            snippet = ""
            pages = []

            if aku_index:
                aku_facts = _get_aku_facts_for_entity(entity, doc_id, aku_index)
                if aku_facts:
                    snippet, pages = _build_snippet_from_akus(entity, doc_id, aku_facts)

            if not snippet:
                entity_pages = _find_entity_pages(entity, doc_id, graph)
                if entity_pages:
                    snippet, pages = _build_snippet_from_pages(entity, doc_id, entity_pages, graph)

            if snippet:
                doc_snippets.append({"doc_id": doc_id, "snippet": snippet})
                for p in pages:
                    source_pages.append({"doc_id": doc_id, "page": p})

        if len(doc_snippets) < 2:
            continue

        # Build prompt for Haiku
        snippets_text = "\n".join(f"Document {s['doc_id'][:16]}:\n{s['snippet']}" for s in doc_snippets)
        prompt = (
            f"Given the following text snippets about '{entity}' from different legal documents, "
            f"write ONE concise bridging fact (1-2 sentences) that connects the information across documents. "
            f"Focus on how the entity relates across documents.\n\n{snippets_text}\n\nBridging fact:"
        )

        try:
            response = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            fact_text = response.content[0].text.strip()
        except Exception as e:
            print(f"  LLM error for entity '{entity}': {e}", file=sys.stderr)
            # Fallback to deterministic
            fact_text = f"{entity} — " + " || ".join(f"[{s['doc_id'][:16]}]: {s['snippet']}" for s in doc_snippets)

        facts.append(
            {
                "fact": fact_text,
                "source_docs": doc_ids,
                "source_pages": source_pages,
                "bridge_entity": entity,
            }
        )

    return facts


def main():
    parser = argparse.ArgumentParser(description="Generate bridging facts from cross-reference graph")
    parser.add_argument("--llm", action="store_true", help="Use Haiku for natural-language bridging facts")
    parser.add_argument("--max-entities", type=int, default=0, help="Max bridge entities to process (0=all)")
    args = parser.parse_args()

    if not GRAPH_PATH.exists():
        print(f"Error: {GRAPH_PATH} not found. Run build_cross_reference_graph.py first.", file=sys.stderr)
        sys.exit(1)

    print("Loading cross-reference graph...")
    graph = load_graph()
    bridge_entities = graph.get("_bridge_entities", {})
    print(f"  Found {len(bridge_entities)} bridge entities")

    aku_index = load_aku_index()
    if aku_index:
        print(f"  Loaded AKU index ({len(aku_index)} documents)")
    else:
        print("  AKU index not found — using raw page text fallback")

    if args.max_entities > 0:
        limited = dict(list(bridge_entities.items())[: args.max_entities])
        bridge_entities = limited
        print(f"  Limited to {len(bridge_entities)} entities")

    mode = "LLM (Haiku)" if args.llm else "deterministic (no-llm)"
    print(f"Generating bridging facts in {mode} mode...")

    if args.llm:
        facts = generate_bridging_facts_llm(bridge_entities, graph, aku_index)
    else:
        facts = generate_bridging_facts_deterministic(bridge_entities, graph, aku_index)

    print(f"  Generated {len(facts)} bridging facts")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(facts, f, indent=2, ensure_ascii=False)

    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
