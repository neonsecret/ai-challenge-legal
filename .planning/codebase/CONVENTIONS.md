# Coding Conventions

**Analysis Date:** 2026-03-23

## Naming Patterns

**Files:**
- Use `snake_case.py` for all modules: `answerer_v3.py`, `llm_reranker.py`, `build_article_index.py`
- Pipeline modules are named by their role: `router.py`, `retriever.py`, `answerer_v3.py`
- Utility/builder scripts use `build_` prefix: `build_article_index.py`, `build_case_index.py`, `build_law_index_v2.py`
- LLM wrappers use `llm_` prefix: `llm_anthropic.py`, `llm_reranker.py`, `llm_router.py`
- Test files use `test_` prefix in `tests/` directory: `tests/test_agent_tools.py`

**Functions:**
- Use `snake_case` for all functions: `retrieve_pages()`, `generate_answer()`, `route()`
- Private/internal functions use `_` prefix: `_get_client()`, `_fallback_route()`, `_is_trick_question()`
- Builder/helper functions use descriptive verbs: `_load_doc_date_pages()`, `_extract_answer_keywords()`
- Getter functions for lazy singletons: `get_reranker()`, `get_embedding_model()`, `get_collection()`

**Variables:**
- Module-level caches use `_` prefix and `snake_case`: `_doc_index`, `_bm25_index`, `_collection`, `_reranker`
- Module-level locks use `_` prefix with `_lock` suffix: `_bm25_lock`, `_collection_lock`, `_reranker_lock`
- Constants use `UPPER_SNAKE_CASE`: `CHROMA_DIR`, `EMBEDDING_MODEL`, `MAX_RETRIES`, `DOCUMENTS_DIR`
- Environment-driven config: `MODEL = "claude-sonnet-4-6"`, `MODEL_FREE_TEXT = os.environ.get("MODEL_FREE_TEXT", "claude-opus-4-6")`

**Types/Classes:**
- Use `PascalCase` for dataclasses and classes: `PageResult`, `RouteResult`, `AnswerResult`, `FormatGuardian`, `FormatIssue`
- Dataclasses are the primary structured type (no Pydantic): `@dataclass` with typed fields

**Regex Patterns:**
- Named with `UPPER_SNAKE_CASE` suffix `_PATTERN` or `_RE`: `CASE_ID_PATTERN`, `ARTICLE_PATTERN`, `_CRIMINAL_PREFIX_RE`
- Pre-compiled at module level for performance: `re.compile(r"...", re.IGNORECASE)`

## Code Style

**Formatting:**
- Ruff is the formatter and linter (configured in `pyproject.toml`)
- Line length: 120 characters (but `E501` line-too-long is ignored, so longer lines are tolerated)
- Target Python version: 3.13

**Linting:**
- Ruff rules enabled: `E` (pycodestyle errors), `F` (pyflakes), `I` (isort), `W` (warnings)
- `E501` (line length) is explicitly ignored
- Config location: `pyproject.toml` under `[tool.ruff]` and `[tool.ruff.lint]`

**Type Hints:**
- Modern Python 3.10+ union syntax: `list[str] | None`, `dict[str, int]`, `tuple[int | None, str]`
- Used on function signatures but not exhaustively on local variables
- `from typing import Any, Dict, List, Optional, Tuple` used in `format_guardian.py` (older style); newer modules use built-in generics

## Import Organization

**Order:**
1. Standard library: `import json`, `import os`, `import re`, `import time`, `import asyncio`, `import sys`
2. Third-party: `import anthropic`, `import chromadb`, `import bm25s`, `import pymupdf`
3. Local project: `from indexer import build_index, CHROMA_DIR`, `from format_guardian import FormatGuardian`

**Style:**
- Prefer `import module` for standard library
- Prefer `from module import specific_name` for local project imports
- `from dotenv import load_dotenv` followed by `load_dotenv()` at module top level in files that need env vars (`finals.py`, `retriever.py`, `indexer.py`)
- Lazy imports inside functions to avoid circular dependencies or optional deps:
  ```python
  def _get_llm_fn():
      try:
          import llm_router
          return llm_router.call_llm
      except ImportError:
          import llm_anthropic
          return llm_anthropic.call_llm
  ```

**Path Aliases:**
- None. All imports are direct module names (flat project structure).

## Module Organization

**Pattern: Module-level initialization**
- Data indices are loaded at import time using top-level code blocks:
  ```python
  _ARTICLE_INDEX: dict = {}
  _article_path = os.path.join(_DATA_DIR, "article_page_index.json")
  if os.path.exists(_article_path):
      with open(_article_path) as _f:
          _ARTICLE_INDEX = json.load(_f)
  ```
- This pattern appears in `answerer_v3.py`, `retriever.py`, `router.py`, `finals.py`

**Pattern: Lazy singleton with double-checked locking**
- Used for expensive ML models and API clients:
  ```python
  _reranker = None
  _reranker_lock = threading.Lock()

  def get_reranker() -> CrossEncoder:
      global _reranker
      if _reranker is None:
          with _reranker_lock:
              if _reranker is None:
                  _reranker = CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=1024)
      return _reranker
  ```
- Found in `retriever.py` for: reranker, embedding model, ChromaDB collection, BM25 index

**Pattern: Lazy singleton without locking**
- Used for API clients (single-threaded access assumed):
  ```python
  _client: anthropic.Anthropic | None = None

  def _get_client() -> anthropic.Anthropic:
      global _client
      if _client is None:
          _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"), timeout=120.0)
      return _client
  ```
- Found in `answerer_v3.py`, `llm_anthropic.py`, `retriever.py`

**Section separators:**
- Use comment blocks with `# ----...` (71+ dashes) to separate logical sections within files
- Each section has a title comment: `# Configuration`, `# Data indices`, `# Core reranking function`

**Dataclass usage:**
- `@dataclass` for structured results: `PageResult`, `RouteResult`, `AnswerResult`, `FormatIssue`
- `field(default_factory=list)` for mutable defaults
- No frozen dataclasses (all are mutable)

## Configuration Patterns

**Environment Variables:**
- Loaded via `python-dotenv`: `load_dotenv()` at module top
- Accessed via `os.environ.get("KEY", "default")` with sensible defaults:
  ```python
  MODEL_FREE_TEXT = os.environ.get("MODEL_FREE_TEXT", "claude-opus-4-6")
  EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
  LLM_RERANK_MODEL = os.environ.get("LLM_RERANK_MODEL", "claude-haiku-4-5-20251001")
  ```
- `.env` file present at project root (existence only noted)

**Constants:**
- Defined at module level as `UPPER_SNAKE_CASE`
- Numeric thresholds inline with comments explaining their purpose:
  ```python
  MAX_RETRIES = 2
  RETRY_DELAYS = [2, 5]  # seconds between retries
  MAX_RETRIES_RATE_LIMIT = 3
  RETRY_DELAYS_RATE_LIMIT = [10, 30, 60]  # exponential backoff for rate limits
  ```

**CLI Arguments:**
- `argparse` in entry-point scripts: `finals.py`, `format_guardian.py`, `prepare_corpus.py`
- Pattern: `parser = argparse.ArgumentParser(description=...)` then `parser.add_argument(...)`
- Key flags in `finals.py`: `--workers`, `--questions`, `--output`, `--skip-indexing`

**Paths:**
- Mix of `os.path.join()` and `pathlib.Path` depending on the file
- `router.py` uses `Path(__file__).parent / "data"` (pathlib style)
- `retriever.py`, `answerer_v3.py` use `os.path.join(os.path.dirname(__file__), "data", ...)`
- Convention: use whichever is already in the file; no strict rule

## Error Handling

**Pattern 1: Graceful degradation with fallback**
- The primary error handling strategy. On failure, fall back to simpler behavior:
  ```python
  try:
      from router import route as _route
      route_fn = _route
  except ImportError:
      print("  WARNING: router.py not found, using fallback routing", file=sys.stderr)
  ```
- `finals.py` has full fallback chain: module import failure -> fallback function -> null answer
- `llm_reranker.py`: LLM rerank failure -> return original cross-encoder order
- `page_verifier.py`: PDF read failure -> return empty string

**Pattern 2: Retry with exponential backoff for API calls**
- Used for Anthropic API calls with rate limit awareness:
  ```python
  for attempt in range(max_retries + 1):
      try:
          return llm_anthropic.call_llm(...)
      except Exception as exc:
          logger.warning(f"[LLM] Attempt {attempt + 1} failed: {exc}")
          if _is_rate_limit(exc):
              continue
          if attempt >= MAX_RETRIES:
              break
  raise last_exc
  ```
- Specific exception types caught: `anthropic.RateLimitError`, `anthropic.APIStatusError`, `json.JSONDecodeError`
- `llm_reranker.py` catches each exception type separately with different retry strategies

**Pattern 3: Broad except with warning log**
- Used for non-critical operations where failure is acceptable:
  ```python
  except Exception as e:
      print(f"  Warning: SAC summary failed for {pdf_id[:16]}: {e}")
      summary = ""
  ```
- Common in index-building scripts and data loading

**Pattern 4: Timeout wrapping for async operations**
- `finals.py` wraps each question in `asyncio.wait_for(..., timeout=600)` with retry:
  ```python
  result = await asyncio.wait_for(
      _process_question_inner(...),
      timeout=600,
  )
  ```
- On timeout: retry up to 2 times, then try Sonnet fallback, then null answer

**Pattern 5: Bare except (avoid)**
- One instance in `format_guardian.py`: `except:` (line 99) -- bare except should be `except Exception:`

## Logging

**Framework:** Python stdlib `logging` module

**Setup:**
- Each module creates its own logger: `logger = logging.getLogger(__name__)`
- Found in: `router.py`, `retriever.py`, `answerer_v3.py`, `llm_reranker.py`, `llm_router.py`, `page_verifier.py`

**Patterns:**
- `logger.info()` for significant pipeline events: page selections, reranking results
- `logger.warning()` for recoverable errors: API failures, parse errors, fallback triggers
- `logger.debug()` for detailed tracing: individual page scores, cache hits
- `print()` for user-facing progress: step headers, timing, summary stats
- `print(..., file=sys.stderr)` for error/warning messages in `finals.py`
- f-strings used in log messages (not lazy % formatting): `logger.warning(f"[LLM] Attempt {attempt + 1} failed: {exc}")`

**Log prefixes:**
- Square bracket tags identify the subsystem: `[llm_rerank]`, `[LLM]`, `[page_verifier]`, `[Decompose]`
- Example: `logger.info("[llm_rerank] %.0fms | %d candidates | %s", elapsed_ms, len(pages), ranking_summary)`

## Comments

**When to Comment:**
- Inline comments explain WHY, not WHAT: `# tokenizer is not thread-safe`, `# 2000 chars = 500-700 tokens`
- Constants have rationale comments: `# seconds between retries`, `# exponential backoff for rate limits`
- Legal domain context is commented: `# These concepts do not exist in DIFC law`

**Docstrings:**
- Every module has a module-level docstring explaining purpose
- Public functions have docstrings (usually one-line or brief paragraph)
- `llm_reranker.py` uses NumPy-style docstrings with Parameters/Returns/Notes sections
- Most functions use simple docstring style without formal parameter docs

## Function Design

**Size:** Functions range from 5 to 80+ lines. Long functions exist in `finals.py` (`_process_question_inner`) and `answerer_v3.py` (`generate_answer`).

**Parameters:** Use keyword arguments with defaults for optional params:
```python
def retrieve_pages(question: str, target_doc_ids: list[str] | None = None,
                   max_per_doc: int = 1, max_total: int = 3,
                   answer_type: str = "", ...) -> list[PageResult]:
```

**Return Values:**
- Dataclasses for complex results: `PageResult`, `RouteResult`, `AnswerResult`
- Tuples for LLM call results: `tuple[str, float, float, float, int, int]` (text, ttft, total, tpot, in_tokens, out_tokens)
- `None` for "not found" cases

## Module Design

**Exports:** No `__all__` defined in any module. All public names are importable.

**Barrel Files:** None. Flat project structure with direct imports.

**Entry Points:**
- `finals.py` is the main orchestrator (has `if __name__ == "__main__":`)
- `format_guardian.py`, `prepare_corpus.py`, `build_article_index.py` are standalone scripts
- Each script uses `argparse` for CLI interface

---

*Convention analysis: 2026-03-23*
