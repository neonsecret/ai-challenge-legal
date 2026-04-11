"""Text processing constants for the Vitreon Legal RAG pipeline.

All truncation limits, token budgets, and text size boundaries in one place.
Each constant documents WHY this specific value was chosen, referencing the
model constraint or design decision it derives from.

Migration note: existing code still uses raw literals in many places.
Import from here when touching those files. See TRUNCATION_AUDIT.md for the
full inventory.
"""

# ═══════════════════════════════════════════════════════════════════════════
# Embedding Pipeline
# Model: Qwen3-Embedding-8B (Q4_K_M GGUF via llama-server)
# Architecture context window: 40,960 tokens (GGUF); practical limit ~32K.
# Czech legal text tokenizes at ~1.8-2.0 chars/token (measured empirically).
# ═══════════════════════════════════════════════════════════════════════════

EMBEDDING_MAX_TOKENS: int = 32_768
"""Practical token budget per llama-server embedding slot.
The GGUF model supports 40,960 but we leave headroom for special tokens."""

EMBEDDING_CHARS_PER_TOKEN_CZECH: float = 1.8
"""Conservative chars-per-token ratio for Czech legal text.
Measured across statute + court-decision corpora. Slovak/English text
is closer to 2.0-3.0; Czech diacritics push it lower."""

# ═══════════════════════════════════════════════════════════════════════════
# Cross-Encoder Reranker
# Model: Qwen3-Reranker-0.6B (via llama-server on port 8089)
# Architecture max_length: 1024 tokens (qwen3_reranker.py tokenizer).
# ═══════════════════════════════════════════════════════════════════════════

RERANKER_MAX_TOKENS: int = 1024
"""Tokenizer max_length for the Qwen3-Reranker-0.6B cross-encoder.
This is the model's trained sequence length; increasing it yields garbage."""

RERANKER_MAX_CHUNK_CHARS: int = 1500
"""Pre-truncation applied to chunk text before cross-encoder scoring.
~833 tokens at 1.8 chars/token; leaves room for the query prefix.
TODO: SUBOPTIMAL — the reranker can handle ~3000 chars of document text
after the query prefix. Increase to 3000 to use more of the context window.
(TRUNCATION_AUDIT #1)"""

# ═══════════════════════════════════════════════════════════════════════════
# Case Law Search Results (agent tool output)
# ═══════════════════════════════════════════════════════════════════════════

CASELAW_SEARCH_PREVIEW_CHARS: int = 3000
"""Max chars of full_text shown in search results when legal_thesis is NULL.
99.7% of court decisions lack a legal_thesis summary; this provides
a preview of the full text so the LLM can assess relevance. 3000 chars
≈ 1700 tokens — enough for the ruling header and beginning of reasoning."""

# ═══════════════════════════════════════════════════════════════════════════
# LLM Reranker (Haiku secondary scoring pass)
# Model: Claude Haiku 4.5 (200K context)
# Cost-controlled: called per-query on top-k candidates.
# ═══════════════════════════════════════════════════════════════════════════

LLM_RERANKER_MAX_PAGE_CHARS: int = 1500
"""Max chars of page text sent to Haiku per reranker candidate.
1500 chars ~ 375 tokens. At 3 candidates: ~1125 tokens input.
Env-var overridable via LLM_RERANK_MAX_CHARS. Justified: this is a
secondary scoring pass after the cross-encoder — 1500 chars is sufficient
for the LLM to confirm the cross-encoder's ranking."""

# ═══════════════════════════════════════════════════════════════════════════
# Answerer (Claude Sonnet 4.6 via Vertex AI — 200K token context)
# ═══════════════════════════════════════════════════════════════════════════

ANSWERER_CONDITION_MAX_CHARS: int = 200
"""Max chars per condition note injected into the answerer prompt.
TODO: SUBOPTIMAL — legal conditions can be complex multi-clause statements.
200 chars may cut off important qualifiers. Increase to 500. Three
conditions at 500 chars = 1500 chars — negligible in a 200K context.
(TRUNCATION_AUDIT #11)"""

ANSWERER_MAX_CONDITIONS: int = 3
"""Max number of condition notes appended to the answerer prompt.
Keeps the prompt concise; more than 3 conditions are rare in practice."""

ANSWERER_SOURCE_EXCERPT_CHARS: int = 2500
"""Max chars of source text sent to the self-critique LLM.
TODO: SUBOPTIMAL — if the answer cites evidence beyond char 2500, the
critique LLM can't verify it. Increase to 5000-8000. The critique is
called once per answer — cost is negligible. (TRUNCATION_AUDIT #7)"""

ANSWERER_TITLE_MAX_CHARS: int = 200
"""Max chars for law/case title extraction.
Justified: titles never exceed 200 chars in any corpus."""

ANSWERER_TITLE_TEXT_MAX_CHARS: int = 500
"""Max chars for title regex matching text.
Justified: title patterns always appear in the first few hundred chars."""

# ═══════════════════════════════════════════════════════════════════════════
# Evidence Verifier (semantic similarity via embedding)
# Model: Qwen3-Embedding-8B (8192 token context, ~24K chars)
# ═══════════════════════════════════════════════════════════════════════════

EVIDENCE_VERIFIER_ANSWER_MAX_CHARS: int = 500
"""Max chars of answer text embedded for semantic verification.
TODO: SUBOPTIMAL — the embedding model handles 8192 tokens (~24K chars).
500 chars means verification only considers the opening of the answer.
Less critical since competition answers are typically <700 chars.
(TRUNCATION_AUDIT #3)"""

EVIDENCE_VERIFIER_PAGE_TEXT_MAX_CHARS: int = 500
"""Max chars of page text embedded for semantic verification.
TODO: SUBOPTIMAL — should be removed entirely or increased to 4000+ chars.
For pages where evidence is in the middle or end, verification misses it
and produces false-negative scores. (TRUNCATION_AUDIT #3)"""

# ═══════════════════════════════════════════════════════════════════════════
# Page Verifier (LLM-based candidate page selection)
# Model: Claude Haiku 4.5 (200K token context)
# ═══════════════════════════════════════════════════════════════════════════

PAGE_VERIFIER_PAGE_TEXT_MAX_CHARS: int = 500
"""Max chars per candidate page sent to the LLM verifier.
TODO: BUG — 500 chars is far too little. Even with 10 candidates at 500
chars each, that's only ~1250 tokens — a negligible fraction of Haiku's
200K context. Increase to 3000. (TRUNCATION_AUDIT #4)"""

PAGE_VERIFIER_ANSWER_MAX_CHARS: int = 400
"""Max chars of the answer sent to the page verifier.
TODO: BUG — 400 chars may cut off citation details the LLM needs to match
against candidate pages. Increase to 1000. (TRUNCATION_AUDIT #4)"""

# ═══════════════════════════════════════════════════════════════════════════
# Speed Agent (Gemini Flash Lite — 1M token context)
# ═══════════════════════════════════════════════════════════════════════════

SPEED_AGENT_PAGE_TEXT_MAX_CHARS: int = 2000
"""Max chars per page in the speed agent's LLM context.
TODO: BUG — Gemini Flash Lite has a 1M token context. 2000 chars (~500
tokens) silently discards most of each legal page (5000-10000+ chars).
The LLM answers from incomplete documents. Remove the truncation or
increase to match the main answerer (full page text).
(TRUNCATION_AUDIT #2)"""

# ═══════════════════════════════════════════════════════════════════════════
# Chunker (corpus-specific section splitting)
# ═══════════════════════════════════════════════════════════════════════════

CHUNKER_MAX_SECTION_CHARS: int = 7500
"""Max chars per chunk for statute/legislation corpora (Czech, UK, AU).
Justified: this is the hard upper bound after recursive splitting.
Statutes rarely have sections this long; when they do, the chunker
splits recursively at sentence boundaries."""

CHUNKER_OVERLAP_CHARS: int = 200
"""Overlap between adjacent chunks in the corpus-specific chunkers.
Ensures cross-chunk retrieval doesn't miss boundary sentences.
Used by Czech and UK chunkers."""

CHUNKER_GENERIC_MAX_CHARS: int = 500
"""Default max_chars for the generic page-level chunker (DIFC PDFs).
TODO: SUBOPTIMAL — 500 chars splits legal articles mid-sentence.
If the generic chunker is applied to new corpora, increase to 2000.
(TRUNCATION_AUDIT #15)"""

CHUNKER_GENERIC_OVERLAP_CHARS: int = 0
"""Default overlap for the generic page-level chunker.
TODO: SUBOPTIMAL — zero overlap means boundary sentences are missed.
Increase to 200 if the generic chunker sees real use.
(TRUNCATION_AUDIT #15)"""

# ═══════════════════════════════════════════════════════════════════════════
# Indexing — AKU extraction, case metadata, document classification
# Model: Claude Haiku 4.5 (200K token context, max_tokens=2048 output)
# ═══════════════════════════════════════════════════════════════════════════

INDEXER_AKU_PAGE_TEXT_MAX_CHARS: int = 4000
"""Max chars per page sent to Haiku for Atomic Knowledge Unit extraction.
TODO: SUBOPTIMAL — Haiku has 200K tokens. Pages exceeding 4000 chars have
their tail content unindexed. Increase to 8000 or remove — cost is per-page
during indexing (one-time), not per-query. (TRUNCATION_AUDIT #8)"""

INDEXER_CLASSIFICATION_TEXT_MAX_CHARS: int = 2000
"""Max chars of first page for document type classification (CASE/LAW/REGULATION).
Justified: type indicators ("DIFC LAW NO.", "Consolidated Version", etc.)
always appear in the first few hundred chars."""

INDEXER_METADATA_EXTRACT_MAX_CHARS_PER_PAGE: int = 2000
"""Max chars per page for case metadata extraction.
TODO: SUBOPTIMAL — metadata (party names, judgment details) can appear
deeper in the first pages. Increase to 4000 for extraction.
Classification (first_page[:2000]) can stay at 2000.
(TRUNCATION_AUDIT #10)"""

INDEXER_SAC_SUMMARY_TEXT_MAX_CHARS: int = 2000
"""Max chars of first pages sent to generate a 200-char retrieval index entry.
Justified: the summary only needs document type, key identifier, and topic —
all present in the opening text. The LLM output is capped at 80 tokens."""

# ═══════════════════════════════════════════════════════════════════════════
# Follow-ups (UX feature, not accuracy-critical)
# Model: Claude Haiku 4.5
# ═══════════════════════════════════════════════════════════════════════════

FOLLOW_UP_ANSWER_PREVIEW_CHARS: int = 2000
"""Max chars of answer text sent for follow-up question generation.
Justified: follow-ups are a UX feature. The first 2000 chars capture
the main points. Keeping the prompt short keeps latency low."""

# ═══════════════════════════════════════════════════════════════════════════
# Multi-turn Conversation Enrichment
# Used for embedding-based retrieval routing of follow-up queries.
# Model context: Qwen3-Embedding-8B (8192 tokens)
# ═══════════════════════════════════════════════════════════════════════════

MULTI_TURN_PRIOR_ANSWER_PREVIEW_CHARS: int = 300
"""Max chars per previous answer appended to follow-up queries for routing.
TODO: SUBOPTIMAL — if key legal references (law name, article number, case
citation) appear after char 300, follow-up queries lose the routing signal.
Increase to 1000 (~500 extra tokens, well within embedding context).
(TRUNCATION_AUDIT #9)"""

MULTI_TURN_MAX_PRIOR_ANSWERS: int = 2
"""Number of most recent assistant answers included in the enriched query.
Justified: older context degrades routing signal; 2 answers is sufficient
to maintain conversation coherence."""

# ═══════════════════════════════════════════════════════════════════════════
# Conversation Storage (PostgreSQL TEXT columns)
# ═══════════════════════════════════════════════════════════════════════════

CONVERSATION_QUESTION_MAX_CHARS: int = 2000
"""Max chars for stored questions. Matches the API-layer validation
(max_length=2000 in neolex/schemas/query.py). DB column is unbounded TEXT."""

CONVERSATION_ANSWER_MAX_CHARS: int = 8000
"""Max chars for stored answers. Generous: competition answers are <700 chars,
web-mode answers rarely exceed 4000. DB column is unbounded TEXT."""

CONVERSATION_MAX_HISTORY_TURNS: int = 10
"""Max messages loaded per conversation (5 Q&A pairs).
Controls worst-case context size for agent cost control."""

# ═══════════════════════════════════════════════════════════════════════════
# Observability (Langfuse trace truncation)
# These do NOT affect RAG pipeline output — logging only.
# ═══════════════════════════════════════════════════════════════════════════

TRACE_OUTPUT_TEXT_MAX_CHARS: int = 5000
"""Max chars of output text logged to Langfuse generation/finalize spans.
Justified: same rationale — logging only, doesn't affect pipeline output."""

# ═══════════════════════════════════════════════════════════════════════════
# Retriever Pattern Matching
# ═══════════════════════════════════════════════════════════════════════════

RETRIEVER_PREFIX_MATCH_CHARS: int = 200
"""Max chars checked for pattern matching (SAC prefix, FINES keyword).
Justified: these patterns always appear in the first 200 chars by design."""
