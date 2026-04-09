# Truncation Audit

Comprehensive audit of all hardcoded truncation patterns in the codebase.
Performed 2026-04-08. Each entry is classified as:

- **BUG**: truncation limit doesn't match the actual constraint
- **SUBOPTIMAL**: limit is within the constraint but wastes available capacity
- **JUSTIFIED**: limit matches the actual constraint and is appropriate
- **STALE**: references old configs that no longer apply

---

## P0 — Active Data Loss

### 1. Reranker chunk text truncation — `SUBOPTIMAL`

| | |
|---|---|
| **Files** | `arlc/retriever.py:265`, `:2803`, `:2841` |
| **Code** | `chunk["text"][:1500]` |
| **Current limit** | 1500 chars (~375 tokens) |
| **Actual constraint** | Qwen3-Reranker-0.6B context window is 1024 tokens (~3000-4000 chars). llama-server reranker runs with its own context window. |
| **Impact** | Chunks can be up to 7500 chars (statute) or 11K-50K chars (court decisions). If the relevant passage starts after char 1500, the reranker scores the chunk as irrelevant and it drops from top-k. The right document may never surface. |
| **Recommended fix** | Increase to at least 3000 chars to use more of the reranker's context window. Make it a named constant `RERANKER_MAX_CHUNK_CHARS` in a constants module with reasoning. Also consider intelligent truncation (e.g., keep first + last N chars, or use query-aware windowing). |

### 2. Speed agent LLM context — `BUG`

| | |
|---|---|
| **File** | `speed_agent/fast_pipeline.py:1564` |
| **Code** | `context_parts.append(f"[Doc {did[:16]}... p.{pn}]\n{text[:2000]}")` |
| **Current limit** | 2000 chars per page |
| **Actual constraint** | Gemini Flash Lite context window is 1M tokens. Even Claude's context is 200K tokens. 2000 chars (~500 tokens) is a tiny fraction. |
| **Impact** | The LLM answers from incomplete documents. Legal pages can be 5000-10000+ chars. This silently discards content that may contain the answer. |
| **Recommended fix** | Remove the truncation or increase to match the main answerer (which sends full page text). This is the same class of bug as the original `[:2000]` embedding truncation. |

### 3. Evidence verifier semantic scoring — `SUBOPTIMAL`

| | |
|---|---|
| **File** | `arlc/evidence_verifier.py:91-92` |
| **Code** | `a_emb = embed_query(answer[:500])` / `p_emb = embed_query(page_text[:500])` |
| **Current limit** | 500 chars (~125 tokens) for both answer and page text |
| **Actual constraint** | Qwen3-Embedding-8B context window is 8192 tokens (~24K chars). The embedding server currently runs with 131072 tokens. |
| **Impact** | Semantic verification only considers the first 500 chars. For pages where evidence is in the middle or end (common in legal text), the verification misses it entirely and produces false-negative scores. |
| **Recommended fix** | Remove the truncation entirely — let the embedding model handle its own context window. At minimum increase to 4000+ chars for page text. Answer truncation is less critical since answers are typically <700 chars in competition mode. |

### 4. Page verifier text — `BUG`

| | |
|---|---|
| **File** | `arlc/page_verifier.py:497` (page text), `:507` (answer) |
| **Code** | `candidates.append((p, text[:500]))` / `f"Answer: {str(answer)[:400]}"` |
| **Current limit** | 500 chars per candidate page, 400 chars for answer |
| **Actual constraint** | The LLM (Claude Haiku) has a 200K token context. Even with 10 candidate pages, 500 chars each is only 5000 chars (~1250 tokens) — a negligible fraction. |
| **Impact** | If supporting evidence is beyond char 500 in a page, the LLM verifier can't find it and selects the wrong page. Directly impacts G-score (citation accuracy). |
| **Recommended fix** | Increase page text to at least 3000 chars (still only ~7500 tokens for 10 pages — well within Haiku's context). Keep the 10-page scan limit for cost control, but give each page sufficient text. |

---

## P1 — Moderate Data Quality Risk

### 5. llama-server docstring context window — `STALE`

| | |
|---|---|
| **File** | `neolex/embeddings/llama_embedder.py:17-23` |
| **Code** | Docstring: `--embedding --pooling last -ngl 99 -c 4096 --port 8088` |
| **Current state** | The docstring says `-c 4096` but the running server was deployed with `-c 131072`. |
| **Impact** | No runtime impact — this is a stale docstring. Misleads developers reading the code. |
| **Recommended fix** | Update the docstring to reflect the actual deployed config (`-c 131072`). |

### 6. UK chunker silent truncation — `BUG`

| | |
|---|---|
| **File** | `scripts/chunk_uk_corpus.py:319-321` |
| **Code** | `c["text"] = c["text"][:MAX_SECTION_CHARS]` (MAX_SECTION_CHARS = 7500) |
| **Current limit** | 7500 chars hard truncation |
| **Actual constraint** | The Czech chunker uses `assert` (crashes on oversized), the AU chunker only logs. The UK chunker silently truncates. |
| **Impact** | UK legislation sections that exceed 7500 chars after recursive splitting lose their tail content silently. |
| **Recommended fix** | Re-split oversized chunks instead of truncating. Match the Czech chunker's behavior (fail loudly) or implement a fallback recursive split. |

### 7. Self-critique source excerpt — `SUBOPTIMAL`

| | |
|---|---|
| **File** | `arlc/answerer.py:1631` |
| **Code** | `source_excerpt = source_text[:2500] if source_text else "[no source]"` |
| **Current limit** | 2500 chars |
| **Actual constraint** | Claude Opus has a 200K token context. The critique prompt uses ~300 tokens of instructions. |
| **Impact** | If the answer cites evidence from beyond char 2500 in the source, the critique LLM can't verify it and may incorrectly flag it as unsupported/hallucinated. |
| **Recommended fix** | Increase to 5000-8000 chars. The critique is called once per answer — cost is negligible. |

### 8. AKU extraction page text — `SUBOPTIMAL`

| | |
|---|---|
| **File** | `arlc/indexing/builders/aku_index.py:94` |
| **Code** | `user_message = f"Document: {doc_id}, Page: {page_num}\n\n{text[:4000]}"` |
| **Current limit** | 4000 chars per page |
| **Actual constraint** | Haiku 4.5 has a 200K token context. max_tokens is set to 2048 for output. |
| **Impact** | Pages exceeding 4000 chars have their tail content unindexed as Atomic Knowledge Units, creating knowledge gaps. |
| **Recommended fix** | Increase to 8000 chars or remove truncation. Cost is per-page during indexing (one-time), not per-query. |

### 9. Multi-turn enrichment — `SUBOPTIMAL`

| | |
|---|---|
| **File** | `neolex/services/pipeline.py:57` |
| **Code** | `prev_answers = [t["content"][:300] for t in history if t["role"] == "assistant"][-2:]` |
| **Current limit** | 300 chars per previous answer, last 2 answers |
| **Actual constraint** | This is appended to the user question for routing/retrieval. The embedding model (Qwen3-8B) has 8192 tokens. |
| **Impact** | If key legal references (law name, article number, case citation) appear after char 300, follow-up queries lose the routing signal and the retriever can't find the right documents. |
| **Recommended fix** | Increase to 1000 chars per previous answer. This adds ~500 tokens to the query — well within the embedding context window. |

### 10. Case metadata page text — `SUBOPTIMAL`

| | |
|---|---|
| **File** | `arlc/indexing/builders/case_metadata.py:135` (classify_document), `:182-194` (extract) |
| **Code** | `first_page[:2000]` / `max_chars_per_page=2000` |
| **Current limit** | 2000 chars per page |
| **Actual constraint** | Haiku 4.5 has 200K tokens. Metadata extraction examines 2-3 pages. |
| **Impact** | Case metadata (party names, judgment details, outcome) that appears deeper in the first pages is missed during indexing. |
| **Recommended fix** | Increase `max_chars_per_page` to 4000 for extraction. Classification (`:135`) can stay at 2000 since law indicators appear early. |

### 11. Conditions in answerer — `SUBOPTIMAL`

| | |
|---|---|
| **File** | `arlc/answerer.py:1271` |
| **Code** | `cond_note += f"- {c[:200]}\n"` (up to 3 conditions) |
| **Current limit** | 200 chars per condition, max 3 conditions |
| **Actual constraint** | This is injected into the LLM prompt alongside the full source text. The LLM context (Claude Sonnet) is 200K tokens. |
| **Impact** | Legal conditions can be complex multi-clause statements. 200 chars may cut off important qualifiers ("except where the court determines..." / "provided that the party has filed..."). |
| **Recommended fix** | Increase to 500 chars per condition. Three conditions at 500 chars = 1500 chars — negligible in the LLM context. |

### 12. EMBEDDING_DIM "full" mismatch — `BUG`

| | |
|---|---|
| **File** | `neolex/embeddings/config.py:39-40` |
| **Code** | `EMBEDDING_DIM: int = 8192 if _dim_env == "full" else int(_dim_env)` |
| **Current state** | Default is 1024 (Snowflake backend only). "full" maps to 8192. DB columns are `Vector(4096)`. |
| **Impact** | If someone sets `EMBEDDING_DIM=full`, they'd get 8192-dim vectors vs 4096-dim DB columns, producing garbage similarity scores or insertion errors. No runtime validation exists. |
| **Recommended fix** | Add a startup validation check that `EMBEDDING_DIM` matches the DB column dimension. The "full" value for Snowflake Arctic Embed L v2.0 should be 1024, not 8192. |

### 13. Finetune script wrong domain — `BUG`

| | |
|---|---|
| **File** | `scripts/finetune_legal_embedder.py:51-62` |
| **Code** | `"Given the following passage from an Australian criminal law charge book"` |
| **Current state** | Hardcoded "Australian criminal law" regardless of actual corpus |
| **Impact** | If used for fine-tuning with DIFC/Czech/UK corpora, generates domain-mismatched synthetic training queries. One-time script, so impact is limited to future fine-tuning runs. |
| **Recommended fix** | Make the domain configurable via CLI argument or detect from corpus metadata. |

---

## P2 — Low Risk / Justified

### 14. Qwen3 reranker tokenizer — `JUSTIFIED`

| | |
|---|---|
| **File** | `arlc/qwen3_reranker.py:122` |
| **Code** | `max_length=1024` in tokenizer |
| **Reasoning** | The Qwen3-Reranker-0.6B is a classifier with a fixed architecture. 1024 tokens is a standard cross-encoder input limit. The model was not trained on longer sequences. Combined with the 1500-char pre-truncation (P0 #1), input effectively reaches ~800 tokens for the document after query prefix. |
| **Note** | The pre-truncation at 1500 chars is the real bottleneck — fixing P0 #1 is more impactful than changing this limit. |

### 15. Generic DIFC chunker defaults — `SUBOPTIMAL`

| | |
|---|---|
| **File** | `arlc/indexing/indexer.py:255` |
| **Code** | `max_chars=500, overlap_chars=0` |
| **Current limit** | 500 chars, 0 overlap |
| **Actual constraint** | Corpus-specific chunkers use 7500/200. This is only the default for the generic page-level chunker (DIFC PDFs). |
| **Impact** | Legal articles spanning 500-2000 chars get split mid-sentence. Zero overlap means cross-chunk retrieval misses boundary sentences. |
| **Recommended fix** | Not urgent since DIFC uses page-level chunks, not section-level. If the generic chunker is ever applied to new corpora, increase to 2000/200. |

### 16. Follow-up generation — `JUSTIFIED`

| | |
|---|---|
| **File** | `neolex/services/follow_ups.py:87` |
| **Code** | `answer[:2000]` |
| **Reasoning** | Follow-up question generation is a UX feature, not accuracy-critical. The first 2000 chars (~500 tokens) capture the main points of any answer. Haiku context is not the bottleneck — keeping the prompt short keeps follow-up latency low. |

### 17. Observability truncation — `JUSTIFIED`

| | |
|---|---|
| **File** | `neolex/observability.py:294,297,359` |
| **Code** | `input_text[:2000]`, `output_text[:5000]` |
| **Reasoning** | These are Langfuse logging truncations, not pipeline truncations. They don't affect RAG output. Langfuse has its own storage limits. Keeping trace data small reduces storage costs. |

### 18. Conversation storage — `JUSTIFIED`

| | |
|---|---|
| **File** | `neolex/services/conversation.py:317,325,355,403` |
| **Code** | `question[:2000]`, `answer[:8000]` |
| **Reasoning** | Questions are validated at the API layer (`max_length=2000` in `neolex/schemas/query.py`), so the 2000 char limit is consistent. Answers rarely exceed 700 chars in competition mode or 4000 chars in web mode, so 8000 is generous. The DB column is unbounded TEXT. |

### 19. LLM reranker page text — `JUSTIFIED`

| | |
|---|---|
| **File** | `arlc/llm/reranker.py:42` |
| **Code** | `MAX_PAGE_TEXT_CHARS = int(os.environ.get("LLM_RERANK_MAX_CHARS", "1500"))` |
| **Reasoning** | Comment explains: "1500 chars ~ 375 tokens. At 3 candidates: ~1125 tokens input." This is cost-controlled for Haiku per-query calls. It's also env-var configurable. The LLM reranker is a secondary scoring pass after the cross-encoder — if the cross-encoder already selected the right chunk, 1500 chars is sufficient for the LLM to confirm. |

### 20. Document classification text — `JUSTIFIED`

| | |
|---|---|
| **File** | `arlc/indexing/builders/case_metadata.py:135` |
| **Code** | `first_page[:2000]` |
| **Reasoning** | Document type classification (CASE vs LAW vs REGULATION) uses keyword indicators like "DIFC LAW NO.", "Consolidated Version", etc. These always appear in the first few hundred characters of the first page. 2000 chars is more than sufficient. |

### 21. Indexer SAC summary — `JUSTIFIED`

| | |
|---|---|
| **File** | `arlc/indexing/indexer.py:142` |
| **Code** | `{first_pages_text[:2000]}` |
| **Reasoning** | This generates a 200-char retrieval index entry from the first pages. The summary only needs to capture document type, key identifier, and topic — all present in the opening text. The max_tokens is 80, so even the LLM output is heavily constrained. 2000 chars input is appropriate. |

### 22. Various title extractions in answerer — `JUSTIFIED`

| | |
|---|---|
| **Files** | `arlc/answerer.py:2039,2184,2269,2277` |
| **Code** | Various `title[:200]`, `title_text[:500]` |
| **Reasoning** | These extract law/case titles from the first line or first few hundred chars of a document. Titles never exceed 200 chars. The `[:500]` on title_text is used for regex matching against title patterns, which also appear early. |

### 23. Retriever prefix matching — `JUSTIFIED`

| | |
|---|---|
| **Files** | `arlc/retriever.py:1003`, `:3043` |
| **Code** | `text_lower[:200]`, `ct[:200]` |
| **Reasoning** | These check for specific patterns (SAC prefix, FINES keyword) in the opening of chunk text. The patterns being matched always appear in the first 200 chars by design. |

### 24. Debug/error message truncations — `JUSTIFIED`

| | |
|---|---|
| **Files** | `scripts/benchmark_accuracy.py:215,374`, `scripts/chunk_czech_corpus.py:274`, `scripts/scrape_difc_corpus.py:287`, various test files |
| **Reasoning** | These are all debug logging, error messages, or test assertion context. They don't affect data processing. |

---

## Summary

| Classification | Count | Action Required |
|---|---|---|
| **BUG** | 4 (#2, #6, #12, #13) | Fix immediately |
| **SUBOPTIMAL** | 8 (#1, #3, #7, #8, #9, #10, #11, #15) | Increase limits, create named constants |
| **STALE** | 1 (#5) | Update docstring |
| **JUSTIFIED** | 11 (#14, #16-24) | No change needed, but should use named constants |

All magic numbers should be migrated to a unified constants module (`arlc/constants.py`) with documented reasoning for each value.
