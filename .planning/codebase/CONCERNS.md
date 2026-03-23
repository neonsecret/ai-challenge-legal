# Codebase Concerns

**Analysis Date:** 2026-03-23

## Tech Debt

**Duplicated trick keyword lists between `finals.py` and `answerer_v3.py`:**
- Issue: `_TRICK_KEYWORDS` is defined independently in both `finals.py` (lines 171-220) and `answerer_v3.py` (lines 277-306). The lists are similar but not identical -- `finals.py` has additional entries like `"community service order"`, `"bail application"`, `"criminal liability"`, `"criminal fine"`, `"not guilty verdict"`, `"police arrest"`, `"search warrant"`, `"arrest warrant"`, `"prison term"`, `"custodial sentence"`, `"prosecutor"`, `"prosecution witness"`, and `"prosecution case"`.
- Files: `finals.py`, `answerer_v3.py`
- Impact: Divergence means trick detection behaves differently at answer generation vs post-processing. A question caught by one list but not the other produces inconsistent behavior.
- Fix approach: Extract a single `TRICK_KEYWORDS` constant into a shared module (e.g., `constants.py`) and import it in both files.

**Duplicated DIFC law name lists across modules:**
- Issue: `_DIFC_LAW_NAMES` in `retriever.py` (lines 205-238), `_LAW_NAME_PATTERNS` in `router.py` (lines 124-168), and hardcoded law-to-PDF mappings in `answerer_v3.py` all maintain independent copies of DIFC law names. Adding a new law requires edits in 3+ files.
- Files: `retriever.py`, `router.py`, `answerer_v3.py`
- Impact: Missing a law in one list causes silent retrieval failures for questions about that law (e.g., `answerer_v3.py` line 1826 notes "hardcoded + dynamic" law names).
- Fix approach: Create a canonical `data/law_registry.json` loaded by all modules, or a `law_constants.py` with a single authoritative list.

**`speed_agent/fast_pipeline.py` is a 1775-line standalone reimplementation:**
- Issue: `speed_agent/fast_pipeline.py` reimplements the entire pipeline (routing, retrieval, answering) without sharing any code with the main pipeline (`finals.py`, `router.py`, `retriever.py`). Uses raw `http.client` instead of the Anthropic SDK, uses Gemini Flash Lite instead of Claude, and reads from `page_cache.json` instead of ChromaDB.
- Files: `speed_agent/fast_pipeline.py`, `speed_agent/build_page_cache.py`
- Impact: Bug fixes in the main pipeline are not propagated. The two pipelines can produce different answers for the same question. Maintenance burden is doubled.
- Fix approach: If the speed agent is still needed, extract shared routing/metadata logic into importable modules. If not needed, remove or archive it.

**Disabled pipeline stages left as dead code:**
- Issue: Multiple pipeline stages are explicitly disabled but their code remains:
  - `opus_page_select` (line 1502-1504 in `finals.py`): "DISABLED -- proven to hurt G in 31 warmup submissions"
  - `opus_sasst` rewrite (line 1571-1572 in `finals.py`): "DISABLED -- no Anthropic credits"
  - `page_verifier.py` exists (489 lines) but is never called from `finals.py`
  - `llm_reranker.py` exists (294 lines) but `use_llm_rerank` parameter defaults to `False` everywhere
- Files: `finals.py`, `page_verifier.py`, `llm_reranker.py`
- Impact: Dead code adds cognitive load and confusion about what is actually active in the pipeline.
- Fix approach: Remove disabled code blocks. Move experimental modules to an `experiments/` directory if they should be preserved for reference.

**Indexer uses wrong Anthropic API pattern:**
- Issue: `indexer.py` calls `anthropic.completion()` (lines 48, 99, 129) which is the legacy OpenAI-style API. The Anthropic SDK uses `client.messages.create()`. The `response.choices[0].message.content` access pattern is also OpenAI-style, not Anthropic.
- Files: `indexer.py` (lines 48-55, 99-106, 129-141)
- Impact: These functions will raise `AttributeError` at runtime. The SAC (Summary-Augmented Chunking) and OCR features are effectively broken.
- Fix approach: Replace `anthropic.completion(...)` with the proper `anthropic.Anthropic().messages.create(...)` pattern used in `llm_anthropic.py`.

## Known Bugs

**Indexer SAC/OCR functions use broken API calls:**
- Symptoms: `_generate_doc_summary()`, `_generate_chunk_context()`, and `_ocr_page()` in `indexer.py` will fail with `AttributeError: module 'anthropic' has no attribute 'completion'`.
- Files: `indexer.py` (lines 48, 99, 129)
- Trigger: Running `python indexer.py` to rebuild the index with SAC enabled.
- Workaround: The fast path in `_generate_chunk_context()` (regex header extraction, line 83) works without LLM. Most chunks get context via this path. SAC summaries are simply empty strings when the LLM call fails.

**`format_guardian.py` bare except clause:**
- Symptoms: Line 99 has `except:` (bare except) which silently swallows all exceptions including `KeyboardInterrupt` and `SystemExit`.
- Files: `format_guardian.py` (line 99)
- Trigger: Any unexpected error in boolean conversion.
- Workaround: None needed for correctness, but the bare except should be `except Exception:`.

## Security Considerations

**API keys loaded from environment without validation:**
- Risk: `ANTHROPIC_API_KEY` is read via `os.environ.get("ANTHROPIC_API_KEY")` in three separate files (`llm_anthropic.py` line 18, `retriever.py` line 27, `answerer_v3.py` line 98). If the key is missing, the Anthropic client is created with `api_key=None`, which will fail at the first API call rather than at initialization.
- Files: `llm_anthropic.py`, `retriever.py`, `answerer_v3.py`
- Current mitigation: `dotenv.load_dotenv()` is called in `finals.py`, `retriever.py`, and `indexer.py`.
- Recommendations: Validate API key presence at startup (in `finals.py` main) and fail fast with a clear error message. Remove duplicate client initialization -- use `llm_anthropic.get_client()` everywhere.

**Three separate Anthropic client instances:**
- Risk: `llm_anthropic.py`, `retriever.py`, and `answerer_v3.py` each create their own `anthropic.Anthropic()` client with different timeout values (120s, 30s, 120s). This wastes connections and makes it harder to enforce consistent auth.
- Files: `llm_anthropic.py` (line 17), `retriever.py` (line 26), `answerer_v3.py` (line 97)
- Current mitigation: None.
- Recommendations: Consolidate to a single client factory in `llm_anthropic.py` with a shared connection pool.

**No input sanitization for question text:**
- Risk: Question text is passed directly into regex operations (`re.compile()`, `re.search()`) and LLM prompts. A crafted question with regex metacharacters could cause ReDoS or unexpected routing. A crafted question could contain prompt injection payloads.
- Files: `retriever.py` (line 379), `router.py` (throughout)
- Current mitigation: `retriever.py` line 383 catches `re.error` and falls back to substring matching.
- Recommendations: Escape user input before compiling as regex. Consider prompt injection defenses for LLM calls.

## Performance Bottlenecks

**Cross-encoder reranking with global lock:**
- Problem: `rerank_chunks()` in `retriever.py` (line 115) holds `_reranker_lock` for the entire prediction call. With `--workers 5`, 4 threads block while 1 thread runs the cross-encoder.
- Files: `retriever.py` (lines 114-118)
- Cause: The BGE reranker's tokenizer is not thread-safe, requiring a global lock. The model itself could run in parallel if tokenization were separated.
- Improvement path: Pre-tokenize outside the lock, then run `model.predict()` with batched inputs. Or use a thread-local tokenizer. The `--workers 5` recommendation in CLAUDE.md exists specifically to work around this contention.

**PDF reading on every page verification:**
- Problem: `page_verifier.py` opens and reads entire PDFs on first access to any page (line 43-50). The `_page_text_cache` is a module-level dict with no size limit.
- Files: `page_verifier.py` (lines 25-51)
- Cause: No eviction policy. With 303 documents averaging ~30 pages each, the cache could hold ~9000 page texts in memory.
- Improvement path: Use an LRU cache with a size limit, or share the page cache with `retriever.py`'s `_extract_page_text()` which also reads PDFs independently.

**Duplicate PDF reads across modules:**
- Problem: Three modules independently read PDF pages: `retriever.py` (`_extract_page_text`, line 1071), `page_verifier.py` (`_get_page_text`, line 32), and `answerer_v3.py` (uses page text from retriever). No shared cache.
- Files: `retriever.py`, `page_verifier.py`
- Cause: Each module was developed independently.
- Improvement path: Create a shared `pdf_cache.py` module with a single page text cache used by all modules.

**Full ChromaDB collection loaded into memory:**
- Problem: `_load_all_chunks()` in `retriever.py` (line 157-181) loads ALL chunks from ChromaDB into memory at startup. With 303 documents and ~500-char chunks, this is manageable. At 3000 documents, this could consume several GB.
- Files: `retriever.py` (lines 157-181)
- Cause: Optimization for the current 303-document corpus size.
- Improvement path: For larger corpora, use lazy loading or streaming. The in-memory approach works at current scale.

## Fragile Areas

**Router regex patterns and hardcoded indices:**
- Files: `router.py` (1304 lines), especially lines 22-68 (compiled regex patterns), lines 110-168 (law name patterns), lines 170-218 (metadata indicators)
- Why fragile: The router relies on 10+ compiled regex patterns that must match the exact formatting of case IDs, law names, and article references in the document corpus. New document formats (e.g., a law with a hyphenated name not matching existing patterns) will silently fail routing.
- Safe modification: Add new regex patterns with test cases. Never modify existing patterns without running the full test suite.
- Test coverage: Only `tests/test_case_index.py` and `tests/test_law_index_v2.py` exist. No tests for the routing logic itself.

**Post-processing pipeline in `finals.py` (lines 1488-1700+):**
- Files: `finals.py` (lines 1488-1841)
- Why fragile: The post-processing section (Steps 5, 5b, 5b.3, 5c, 5c.2, 5d, 5e, 5f) is a sequential chain of transformations applied to results after answer generation. Each step mutates the results list in place. A bug in one step corrupts all downstream steps.
- Safe modification: Each post-processing step should be a pure function that takes results and returns new results. Currently, steps use `_working_results` as a mutable shared state.
- Test coverage: No tests for any post-processing step.

**Magic numbers in retriever scoring:**
- Files: `retriever.py`
- Why fragile: Hardcoded thresholds control retrieval behavior:
  - `0.4` low-confidence threshold (line 1157): below this, fallback retrieval activates
  - `2.0` BM25 weight in RRF (line 1021): "raised 1.5->2.0 for larger 300-doc corpus"
  - `0.10` relative score threshold in `_score_doc_by_law_name()` (line 342)
  - `1000` law doc score boost (line 317)
  - `60` RRF k parameter (line 1022)
  - `+1.2` name/names boost (mentioned in CLAUDE.md)
  - `0.05` minimum page score (mentioned in CLAUDE.md)
  These were tuned for the 303-document corpus and may not transfer to a different corpus.
- Safe modification: Extract all magic numbers to a `RETRIEVAL_CONFIG` dict at the top of the file with comments explaining their provenance.

## Scaling Limits

**ChromaDB with in-memory full load:**
- Current capacity: ~303 documents, ~5000 chunks loaded into memory via `_load_all_chunks()`.
- Limit: At ~3000 documents (~50K chunks), the in-memory approach will use significant RAM (estimated 2-4 GB for text + metadata).
- Scaling path: Use ChromaDB's native query API instead of loading everything into memory. Or migrate to a dedicated vector database (Qdrant, Weaviate) with native pagination.

**BM25 index rebuilt on every cold start:**
- Current capacity: ~5000 chunks indexed in seconds.
- Limit: At 50K+ chunks, BM25 indexing takes minutes. The disk cache (`data/bm25_cache/`) helps but is invalidated on every re-index.
- Scaling path: Use incremental BM25 index updates. The `bm25s` library supports this.

**Single-threaded cross-encoder:**
- Current capacity: 15-60 chunks reranked per question in ~1-3 seconds.
- Limit: With 5 concurrent workers, total throughput is limited by the global reranker lock. Effective throughput is ~1 question/second for the reranking step.
- Scaling path: Batch reranking across questions, or use a model server (vLLM, TGI) for the cross-encoder.

## Dependencies at Risk

**PyMuPDF text extraction quality:**
- Risk: PyMuPDF misses structural elements embedded as images (article headers, section numbers). Competitor analysis confirms this was the #1 factor in the 0.719 finals score vs 0.95+ competitors.
- Impact: ~160 wrong-page errors in finals due to invisible text (image-embedded headers not searchable by BM25/vector).
- Migration plan: Replace with Docling + multimodal LLM repair (as competitor `guy4` did) or Gemini vision preprocessing (as competitor `guy1` did). Estimated G impact: +0.05-0.08.

**`bm25s` library:**
- Risk: Niche library with limited community support. No type stubs. API may change.
- Impact: BM25 retrieval is a critical path component.
- Migration plan: Consider `rank_bm25` (more popular) or integrate BM25 directly via a few lines of custom code.

## Missing Critical Features

**Cross-reference resolution at index time (IndexRAG pattern):**
- Problem: Questions requiring cross-document reasoning (e.g., "Which case references Law X?") are handled by runtime routing heuristics in `router.py` (70+ lines of hand-crafted law-name scoring). Competitor `guy2` solved this at index time by generating synthetic bridging facts.
- Blocks: Accurate retrieval for multi-document questions. Current approach requires manual maintenance of routing rules.
- Source: `output/competitor_analysis.md` (Section 3)

**Multi-signal document retrieval fusion:**
- Problem: The pipeline uses a single BM25+vector+cross-encoder chain. Competitor `guy4` used 4 parallel signals with 5-weight fusion, tested across 2300+ configurations. Their finding: "BM25 hurts page ranking" (should be used for doc-level only, not page-level).
- Blocks: Optimal page selection. Current system conflates document identification and page selection into one retrieval step.
- Source: `output/competitor_analysis.md` (Section 2)

**Page verification not deployed:**
- Problem: `page_verifier.py` (489 lines) implements page-answer consistency verification but is never called from the pipeline. Competitor `guy4` used a simpler version: send 8+ pages to LLM, ask which pages it used, intersect with context.
- Blocks: G score improvement. Estimated impact: +0.03-0.06 G.
- Source: `output/competitor_analysis.md` (Section 5)

**Per-document-type retrieval:**
- Problem: `retriever.py` uses a single generic retrieval strategy for all 303 documents. Laws need article-level navigation; cases need section-based retrieval (parties, facts, orders); consultation papers need topic-based retrieval.
- Blocks: Precision for document-type-specific questions.
- Source: `output/competitor_analysis.md` (Section 4)

## Test Coverage Gaps

**No tests for core pipeline logic:**
- What's not tested: `finals.py` (1841 lines), `retriever.py` (1606 lines), `answerer_v3.py` (2152 lines), `router.py` routing logic.
- Files: Only 4 test files exist in `tests/`: `test_agent_tools.py` (81 lines), `test_agent_v2.py` (49 lines), `test_case_index.py`, `test_law_index_v2.py`. These test data index building, not the pipeline.
- Risk: Any change to routing, retrieval, or answering logic can break the pipeline without detection. Post-processing steps in `finals.py` (article page restoration, names normalization, absence detection, trick question handling) are entirely untested.
- Priority: High -- this is the single largest risk factor for regressions.

**No integration tests:**
- What's not tested: End-to-end question processing (route -> retrieve -> answer -> post-process).
- Files: No integration test file exists.
- Risk: Individual components may work in isolation but fail when composed. The `_process_question_inner` async flow in `finals.py` has complex timeout/retry/fallback logic that is never tested.
- Priority: High

**No regression tests for known-good answers:**
- What's not tested: The pipeline's output on previously-submitted questions. The 15 "proven findings" from CLAUDE.md were validated through manual submission, not automated tests.
- Files: No golden-answer test file exists.
- Risk: A change that improves one question type may silently regress another. The "GRAVEYARD" section in CLAUDE.md documents multiple such regressions.
- Priority: Medium -- creating golden tests from past submissions would catch regressions early.

---

*Concerns audit: 2026-03-23*
