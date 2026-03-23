# Ultimate Pipeline Upgrade — PLAN

**Goal**: Apply all competitor insights + post-mortem learnings to build a 0.95+ capable legal RAG pipeline.

**Projected score**: 0.95-0.98 (from current 0.719)
- S_det: 0.98+ (oracle + better retrieval)
- S_asst: 0.85+ (Opus + better context pages)
- G: 0.96+ (multi-signal fusion + page verification + cross-refs)
- F: 1.05 (question sorting + oracle speed)

**Sources**: guy1 (DotaGPT ontology), guy2 (IndexRAG), guy3 (structure-first), guy4 (IAS Partners dual pipeline)

---

## Wave 1: Foundation (no dependencies, all parallel)

### Task 1.1: Docling PDF Extraction Pipeline
**Files**: NEW `docling_converter.py`, MODIFY `indexer.py`, `prepare_corpus.py`
**Inspiration**: guy1 (Gemini PDF), guy3 (Docling + LLM repair), guy4 (Docling + table fixing)
**Why**: Raw PyMuPDF misses image-embedded headers, tables, structural elements. All 3 top competitors used better extraction.

Implementation:
- Install `docling` package (add to pyproject.toml)
- Create `docling_converter.py`:
  - Convert each PDF → structured Markdown via Docling
  - Extract document hierarchy (parts, chapters, articles, sections, schedules)
  - Handle cross-page table continuations
  - Detect and fill text gaps (>20% missing → supplement with PyMuPDF raw text)
  - Remove strikethrough text (legal amendment artifacts)
  - Output: `data/documents_md/{doc_id}/page_{N}.md` + `data/documents_md/{doc_id}/structure.json`
- Wire into `prepare_corpus.py` as Step 1.5 (after PDF download, before indexing)
- Fallback: if Docling fails on a PDF, fall back to PyMuPDF raw extraction
- **Credit**: Docling approach from guy3 (structure-first) and guy4 (IAS Partners)

**Acceptance**: All 303 PDFs converted to Markdown with structural metadata. Article boundaries auto-detected.

### Task 1.2: Custom Legal Tokenizer for BM25
**Files**: NEW `legal_tokenizer.py`, MODIFY `retriever.py`
**Inspiration**: guy4 (IAS Partners custom tokenizer)
**Why**: Standard BM25 tokenization misses compound legal references. "CFI 057/2025" should match "CFI", "057", "2025", and "cfi_057_2025".

Implementation:
- Create `legal_tokenizer.py`:
  - Expand case IDs: `"CFI 057/2025"` → `["CFI", "cfi_057_2025", "057", "2025"]`
  - Expand article refs: `"Article 28(1)"` → `["Article", "28", "1", "article_28_1"]`
  - Expand law numbers: `"DIFC Law No. 4 of 2019"` → `["DIFC", "Law", "4", "2019", "difc_law_4_2019"]`
  - Expand schedule refs: `"Schedule 3"` → `["Schedule", "3", "schedule_3"]`
  - Preserve standard word tokenization for everything else
- Integrate into BM25 index building in `retriever.py`
- **Credit**: Custom legal tokenizer concept from guy4 (IAS Partners)

**Acceptance**: BM25 recall improves on article-reference and case-ID queries.

### Task 1.3: Vertex AI LLM Backend (Flag-Controlled)
**Files**: NEW `llm_vertex.py`, MODIFY `llm_router.py`, `.env.example`
**Inspiration**: User requirement (Vertex AI as a flag)
**Why**: Adds Google Cloud Vertex AI as an alternative LLM backend alongside Anthropic SDK.

Implementation:
- Create `llm_vertex.py`:
  - Uses `google-cloud-aiplatform` SDK or raw REST API
  - Supports Claude models on Vertex AI (claude-sonnet-4-6, claude-opus-4-6)
  - Same `call_llm()` signature as `llm_anthropic.py`
  - Configurable via `VERTEX_PROJECT_ID`, `VERTEX_LOCATION`, `GOOGLE_APPLICATION_CREDENTIALS`
- Modify `llm_router.py`:
  - Add `LLM_BACKEND` env var: `anthropic` (default), `vertex`, `auto`
  - `auto` mode: try Vertex first, fall back to Anthropic SDK
  - Retry logic preserved for both backends
- Update `.env.example` with Vertex config options
- Add `google-cloud-aiplatform` as optional dependency in pyproject.toml

**Acceptance**: Pipeline runs with `LLM_BACKEND=vertex` using Vertex AI, `LLM_BACKEND=anthropic` using Anthropic SDK, `LLM_BACKEND=auto` trying both.

---

## Wave 2: Enhanced Indexing (depends on Wave 1.1)

### Task 2.1: Auto Article-Page Index from Docling Structure
**Files**: MODIFY `build_article_index.py`
**Inspiration**: guy1 (typed ontology), guy3 (structural extraction)
**Why**: Manual article-page index doesn't scale to 303+ docs. Docling structure provides article boundaries automatically.

Implementation:
- Read `data/documents_md/{doc_id}/structure.json` from Task 1.1
- Extract article/section/regulation/schedule headings with their page numbers
- Merge with existing manual corrections (preserve hand-verified entries)
- Output enriched `data/article_page_index.json`
- **Credit**: Auto-extraction approach from guy1 (ontology) and guy3 (structure-first)

**Acceptance**: Article-page index has 95%+ coverage of all law/regulation articles across 303 docs.

### Task 2.2: Cross-Reference Graph (IndexRAG)
**Files**: NEW `build_cross_reference_graph.py`, NEW `data/cross_reference_graph.json`
**Inspiration**: guy2 (IndexRAG paper, arXiv:2603.16415)
**Why**: Cross-document references are our blind spot. IndexRAG resolves them at index time (one-time cost) instead of runtime.

Implementation:
- For each document page, run Haiku to extract:
  - Internal refs: "See Article 15" → target page within same doc
  - External refs: "as defined in the Insolvency Law" → target doc + page
  - Table/schedule linkages: penalty table row → referenced article
  - Defined terms: "Employee" as defined in Law X → source definition page
- Build graph: `{doc_id: {page: [{target_doc, target_page, type, context}]}}`
- Store as `data/cross_reference_graph.json`
- Cost estimate: ~303 docs × ~15 pages × $0.001/page = ~$5 with Haiku
- **Credit**: IndexRAG (Bao & Shi, 2026, arXiv:2603.16415) — bridge entity detection + bridging fact generation

**Acceptance**: Cross-reference graph covers 80%+ of explicit legal cross-references in corpus.

### Task 2.3: AKU Extraction (QA-Structured Facts)
**Files**: NEW `build_aku_index.py`, MODIFY `indexer.py`
**Inspiration**: guy2 (IndexRAG — Atomic Knowledge Units)
**Why**: IndexRAG paper shows QA extraction > chunking > summarization for retrieval (F1: 67.2 vs 63.6 vs 66.0).

Implementation:
- For each PDF page, prompt Haiku:
  ```
  Extract all factual claims from this legal document page as question-answer pairs.
  For each fact: {"q": "...", "a": "...", "page": N, "doc_id": "..."}
  ```
- Store AKUs alongside raw chunks in ChromaDB (tagged as `type: "aku"`)
- Keep raw chunks for BM25 (keyword matching), AKUs for vector retrieval
- Cost: ~303 docs × ~15 pages × $0.001 = ~$5 with Haiku
- **Credit**: AKU concept from IndexRAG (Bao & Shi, 2026)

**Acceptance**: AKU index populated for all 303 docs. Vector search on AKUs returns more relevant results than raw chunks.

### Task 2.4: Bridging Fact Generation
**Files**: MODIFY `build_cross_reference_graph.py`
**Inspiration**: guy2 (IndexRAG Stage 2)
**Why**: Synthetic bridging facts encode cross-document reasoning, making it retrievable in single-pass.

Implementation:
- From Task 2.2's cross-reference graph, identify bridge entities (appear in 2+ docs, ≤10 docs)
- For each bridge entity, collect facts from each doc's AKUs that mention it
- Prompt Haiku to generate bridging facts: merge information across documents
- Store bridging facts in ChromaDB (tagged as `type: "bridge"`)
- Cap at 3 bridging facts per 10 retrieval slots (balanced context selection from IndexRAG)
- **Credit**: Bridging fact generation from IndexRAG (Bao & Shi, 2026)

**Acceptance**: Bridging facts generated for top bridge entities. Multi-hop comparison questions retrieve relevant cross-doc context.

---

## Wave 3: Retrieval Upgrade (depends on Wave 1 + Wave 2)

### Task 3.1: Multi-Signal Document Fusion
**Files**: MODIFY `retriever.py`
**Inspiration**: guy4 (IAS Partners — 4-signal doc fusion, 2300+ configs)
**Why**: Separate document identification from page selection. Our single BM25+vector merge is inferior.

Implementation:
- Add 3 BM25 index variants:
  - `bm25_all` — all pages (existing)
  - `bm25_page1` — first page only (document identification signal)
  - `bm25_doc` — concatenated doc text (document-level matching)
- Document fusion weights (from guy4's empirically tuned values):
  - `0.10 * bm25_std + 0.05 * dense_std + 0.20 * dense_rrf + 0.30 * bm25_doc + 0.30 * bm25_page1`
- Adaptive document selection: 1-3 docs based on 0.15 gap threshold (instead of fixed max-3)
- **Credit**: Multi-signal fusion architecture from guy4 (IAS Partners, Ivanov/Agishev/Sadchikov)

**Acceptance**: Document recall ≥97% on test set. Adaptive selection correctly identifies 1-3 target docs.

### Task 3.2: Dense-Only Page Ranking
**Files**: MODIFY `retriever.py`
**Inspiration**: guy4 (IAS Partners — "BM25 hurts page ranking")
**Why**: guy4 empirically found across 2300+ configs that zeroing BM25 weight for page-level ranking improves results.

Implementation:
- After document fusion selects target docs, rank pages within each doc using:
  - Dense similarity only (no BM25 component)
  - Cross-encoder reranking on top-N dense candidates
  - BM25 weight = 0 for page selection (keep for doc selection)
- Keep cross-encoder as final reranker but feed it better candidates
- **Credit**: Dense-only page ranking insight from guy4 (IAS Partners)

**Acceptance**: Page-level recall improves vs current BM25+vector+cross-encoder approach.

### Task 3.3: Per-Answer-Type Retrieval Configs
**Files**: MODIFY `retriever.py`, `finals.py`
**Inspiration**: guy4 (separate DET vs free-text pipelines), guy3 (specialized retrieval per doc type)
**Why**: DET questions need precise single-page facts; free-text needs broader context.

Implementation:
- DET config: TOP_K=128, 3072-dim embeddings (if using OpenAI), max 3 pages, precision-focused
- Free-text config: TOP_K=64, standard embeddings, max 5 pages, recall-focused
- Name/names config: Include cross-reference graph for comparison questions
- Boolean config: Include metadata-only fast path for cross-case questions
- Config stored as `RETRIEVAL_CONFIGS` dict in `retriever.py`
- `finals.py` passes `answer_type` to retriever for config selection
- **Credit**: Dual-pipeline concept from guy4 (IAS Partners)

**Acceptance**: Each answer type uses optimized retrieval parameters.

### Task 3.4: Cross-Reference-Aware Retrieval
**Files**: MODIFY `retriever.py`
**Inspiration**: guy2 (IndexRAG), guy1 (ontology reference traversal)
**Why**: When retriever selects a page, check cross-reference graph for linked pages that should also be included.

Implementation:
- After page ranking, for each selected page:
  - Look up `cross_reference_graph[doc_id][page]`
  - If references exist, boost referenced pages in ranking
  - For comparison questions (detected by router), always include pages from both referenced docs
- Balanced context: cap cross-ref additions at 1 per 3 retrieval slots
- **Credit**: Cross-reference traversal from guy1 (ontology) + guy2 (IndexRAG)

**Acceptance**: Multi-doc comparison questions cite pages from ALL relevant documents.

---

## Wave 4: Answer Quality + Verification (depends on Wave 3)

### Task 4.1: Deploy Page Verification (Production)
**Files**: MODIFY `page_verifier.py`, `finals.py`
**Inspiration**: guy4 (LLM source_pages intersection), our own post-mortem
**Why**: We built page_verifier.py but never deployed it in production. guy4's simpler approach works.

Implementation:
- Enable `page_verifier.verify_pages()` in production pipeline (currently disabled)
- Two-mode operation:
  - Deterministic mode (default): regex/string matching, 0 PPQ cost
  - LLM mode (flag): send 8+ candidate pages to LLM, ask which support the answer, intersect
- Wire LLM mode into `finals.py` Step 4 with `use_llm_fallback=True` when PPQ budget allows
- Track PPQ impact: LLM verification adds ~0.3 PPQ on average
- Fix Step 3.5 conflict (already done — `_step4_changed` flag skips Step 3.5)
- **Credit**: LLM page intersection approach from guy4 (IAS Partners)

**Acceptance**: Page verification runs on all non-oracle questions. G improves by ≥0.05 on test set.

### Task 4.2: Structured Reasoning Output
**Files**: MODIFY `answerer_v3.py`
**Inspiration**: guy3 ({"reasoning", "answer", "grounding"} schema)
**Why**: Force LLM to cite which pages support each claim before answering. Free page verification without extra LLM call.

Implementation:
- Add `"grounding"` field to answer output schema:
  ```json
  {"reasoning": "...", "answer": "...", "grounding": [{"claim": "...", "page": N}]}
  ```
- Parse grounding field to get LLM-reported page usage
- Use grounding for page verification (complement to page_verifier.py)
- Apply to free_text questions only (deterministic types don't need reasoning)
- **Credit**: Structured reasoning schema from guy3

**Acceptance**: Free-text answers include grounding citations. Grounding-based page selection improves G on free-text subset.

### Task 4.3: Embedding Decontamination
**Files**: MODIFY `indexer.py`
**Inspiration**: guy3 (embedding collapse from metadata contamination)
**Why**: Full-page text includes repeated headers/footers/titles that dominate embedding space, making all pages of the same doc cluster together.

Implementation:
- Before embedding, strip:
  - Document title (repeated on every page)
  - Page headers/footers
  - "DIFC" / "Dubai International Financial Centre" boilerplate
  - Page numbers
- Keep raw text for BM25 (benefits from title matching)
- Embed cleaned content only in ChromaDB
- **Credit**: Metadata contamination insight from guy3

**Acceptance**: Embedding-based page ranking discriminates better within documents.

---

## Wave 5: Polish + Integration Testing

### Task 5.1: End-to-End Integration Test
**Files**: MODIFY `test_regression.py`
**Why**: Verify all upgrades work together without regression.

Implementation:
- Run full pipeline on 50-question test subset
- Compare G, S_det, S_asst against baseline (0.719)
- Verify: Docling extraction → enhanced indexing → multi-signal retrieval → page verification → answer generation
- Performance test: ensure pipeline completes 900 questions in <2 hours with 5 workers

### Task 5.2: Update Documentation
**Files**: MODIFY `README.md`, `CLAUDE.md`, `JOURNEY.md`
**Why**: Document all upgrades, credits, and new configuration options.

Implementation:
- Update README with new architecture diagram
- Add competitor credits section
- Document Vertex AI flag configuration
- Update JOURNEY.md with upgrade narrative

### Task 5.3: Clean Submission Archive
**Files**: MODIFY `Makefile`
**Why**: Ensure the open-source repo is clean and reproducible.

Implementation:
- Add `make upgrade` target for running the full upgrade pipeline
- Add `make benchmark` target for running integration tests
- Verify `make run` still works with default settings

---

## Dependency Graph

```
Wave 1 (parallel):
  1.1 Docling PDF ──┐
  1.2 Legal Tokenizer ──┤
  1.3 Vertex AI LLM ────┤
                        v
Wave 2 (depends on 1.1):
  2.1 Auto Article Index ──┐
  2.2 Cross-Ref Graph ─────┤
  2.3 AKU Extraction ──────┤
  2.4 Bridging Facts ──────┤  (depends on 2.2 + 2.3)
                           v
Wave 3 (depends on 1 + 2):
  3.1 Multi-Signal Fusion ──┐
  3.2 Dense-Only Page Rank ─┤
  3.3 Per-Type Retrieval ───┤
  3.4 Cross-Ref Retrieval ──┤
                            v
Wave 4 (depends on 3):
  4.1 Page Verification ──┐
  4.2 Structured Reasoning ┤
  4.3 Embedding Decontam ──┤
                           v
Wave 5 (depends on all):
  5.1 Integration Test
  5.2 Documentation
  5.3 Clean Archive
```

## Credits

| Technique | Source | Paper/Repo |
|-----------|--------|------------|
| Gemini PDF preprocessing | guy1 (DotaGPT) | Private (Telegram/Habr post) |
| IndexRAG (AKUs, bridging facts) | guy2 | arXiv:2603.16415 (Bao & Shi, Continuum AI) |
| Docling structured extraction | guy3 + guy4 | github.com/DS4SD/docling |
| Per-doc-type specialized retrieval | guy3 | Private (competition takeaways) |
| Multimodal LLM for PDF repair | guy3 | Private |
| Embedding decontamination | guy3 | Private |
| Structured reasoning schema | guy3 | Private |
| Multi-signal doc fusion (5-weight) | guy4 (IAS Partners) | github.com/iamalexandreevich/ai-agentic-legal-rag-hack |
| Dense-only page ranking | guy4 (IAS Partners) | Same repo |
| Dual DET/free-text pipelines | guy4 (IAS Partners) | Same repo |
| Custom legal tokenizer | guy4 (IAS Partners) | Same repo |
| LLM page intersection verification | guy4 (IAS Partners) | Same repo |
| Typed document ontology | guy1 (DotaGPT) | Private |
