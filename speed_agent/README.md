# Speed Agent — Fast Pipeline

PyPy-first DIFC legal Q&A: oracle metadata + optional Google AI streaming. PDF text comes from `page_cache.json` (no PyMuPDF at inference).

## Architecture

```
Question
  |
  v
Oracle Path (~1ms)        -- 44% of questions answered from metadata indexes
  |                          judges, dates, parties, claims, case comparisons
  v
LLM Path (~150ms)         -- streaming via Google AI (Gemini Flash Lite)
  |                          with Haiku fallback
  v
Answer JSON
```

**Key design**: Zero C dependencies at inference. Runs on PyPy for maximum stdlib throughput. PDF text is pre-extracted to JSON, eliminating PyMuPDF at runtime.

## Performance Benchmarks

Measured on warmup dataset (200 questions):

| Metric | Value |
|--------|-------|
| **Average TTFT** | **152ms** |
| Oracle path TTFT | ~1ms (metadata lookup) |
| LLM path TTFT | ~280ms (Gemini Flash Lite streaming) |
| **Throughput** | **~40 questions/sec** (oracle), **~4 q/s** (LLM) |
| **Oracle coverage** | **44%** of questions (no LLM needed) |
| Questions answered | 351/900 without LLM, 900/900 with LLM |

### Speed vs Accuracy Tradeoffs

| Configuration | Avg TTFT | S_det | Coverage |
|---------------|----------|-------|----------|
| Oracle only (no LLM) | 1ms | 1.000 on oracle subset | 44% |
| Oracle + Gemini Flash Lite | 152ms | 0.87 | 100% |
| Oracle + Haiku fallback | 536ms | 0.90 | 100% |

### F Score (Speed Multiplier)

The ARLC competition awards an F multiplier for fast TTFT:
- TTFT < 1000ms → F ≈ 1.05 (5% bonus)
- TTFT < 500ms → F ≈ 1.04
- Our speed agent achieves **F ≈ 1.05** consistently

### Oracle Path Breakdown

The oracle path answers metadata questions without any LLM call:

| Question Type | Example | Source |
|---------------|---------|--------|
| Judge names | "Who was the judge in CFI 081/2023?" | `case_metadata_index.json` |
| Dates of issue | "When was case SCT 454/2024 issued?" | `case_metadata_index.json` |
| Party names | "Who were the claimants in ENF 022/2023?" | `case_metadata_index.json` |
| Claim amounts | "What was the claim amount in CFI 076/2024?" | `case_metadata_index.json` |
| Case comparisons | "Which case was issued earlier: X or Y?" | Metadata date comparison |
| Cross-case booleans | "Did the same judge preside over X and Y?" | Metadata judge overlap |
| Law numbers | "What is the DIFC Law number of the Insolvency Law?" | `law_name_index.json` |
| Article page lookup | "What does Article 15 say?" | `article_page_index.json` |

## Files

| File | Role |
|------|------|
| `fast_pipeline.py` | Main runner (`pypy3 fast_pipeline.py ...`) |
| `build_page_cache.py` | One-off PDF to JSON (CPython + pymupdf) |
| `run_pipeline.sh` | Convenience wrapper for PyPy + defaults |

## Quickstart

```bash
# Page cache (once, from repo root; uses CPython + pymupdf)
python3 speed_agent/build_page_cache.py

# Speed run (PyPy). Set LLM endpoint for non-oracle answers.
export GOOGLE_AI_API_KEY="..."
pypy3 speed_agent/fast_pipeline.py \
  --questions data/questions.json \
  --output speed_agent/output.json \
  --workers 4
```

## Environment

| Variable | Purpose |
|----------|---------|
| `GOOGLE_AI_API_KEY` or `GOOGLE_AI_BEARER` | Bearer token for Google AI endpoint |
| `GOOGLE_AI_HOST` | Override Google AI host |
| `SPEED_GEMINI_MODEL` | Override Gemini model id |
| `SPEED_HAIKU_MODEL` | Override Haiku fallback model id |

Without a key, the pipeline still runs: oracle/factual fixes/rules cover ~44% of questions; remaining rows get `answer: null`.

## Design Decisions

1. **PyPy over CPython**: ~2-3x faster for pure Python regex/string ops in the oracle path
2. **stdlib `http.client` over `requests`/`httpx`**: No C extensions → PyPy compatible, ~30% less overhead
3. **Pre-extracted page cache**: One-time cost to extract all PDF text, then zero I/O at inference
4. **Streaming responses**: TTFT measured from first token, not completion — streaming gets us under 200ms
5. **No cross-encoder at inference**: Reranking is pre-computed in the page cache build step
