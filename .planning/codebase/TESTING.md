# Testing Patterns

**Analysis Date:** 2026-03-23

## Test Framework

**Runner:**
- pytest >= 9.0.2 (dev dependency in `pyproject.toml`)
- Config: No `pytest.ini` or `pyproject.toml` `[tool.pytest]` section -- uses defaults

**Assertion Library:**
- Built-in `assert` statements (pytest native assertions)

**Run Commands:**
```bash
uv run pytest tests/ -v          # Run all tests
uv run pytest tests/ -v -k test_name  # Run specific test
uv run python finals.py --workers 5   # Full pipeline run (integration/eval)
```

## Test File Organization

**Location:**
- Tests live in `tests/` directory (separate from source, not co-located)
- `conftest.py` at project root adds project root to `sys.path`

**Naming:**
- `test_*.py` prefix convention
- Test functions use `test_` prefix with descriptive names: `test_search_within_doc_returns_pages()`

**Structure:**
```
tests/
├── test_agent_tools.py    # Unit tests for agent_tools.py helper functions (81 lines)
├── test_agent_v2.py       # Integration tests for agent_v2.py pipeline (49 lines)
├── test_case_index.py     # Data validation for case_metadata_index.json (19 lines)
└── test_law_index_v2.py   # Data validation for latest_edition_index.json (14 lines)
conftest.py                # Root conftest: adds project root to sys.path
```

## Test Structure

**Suite Organization:**
- No test classes -- all tests are standalone functions
- No `setUp`/`tearDown` or fixtures beyond `conftest.py`
- Tests are independent (no shared state between tests)

**Pattern: Unit test with real data:**
```python
def test_search_within_doc_returns_pages():
    """BM25 search within a real law doc returns ranked pages."""
    idx = json.load(open("data/article_page_index.json"))
    law_doc = next(k for k, v in idx.items() if v.get("type") == "LAW")
    results = search_within_doc(law_doc, "article", top_k=3)
    assert isinstance(results, list)
    assert len(results) > 0
    assert "page_num" in results[0]
    assert "text" in results[0]
```

**Pattern: Graceful handling of missing data:**
```python
def test_search_within_doc_empty_for_fake_doc():
    """search_within_doc returns empty list for non-existent doc."""
    results = search_within_doc("0" * 64, "anything", top_k=3)
    assert results == []
```

**Pattern: Structure/schema validation on data files:**
```python
def test_case_index_structure():
    idx = json.load(open('data/case_metadata_index.json'))
    case = list(idx.values())[0]
    assert 'docs' in case
    for doc in case['docs']:
        assert 'doc_id' in doc
```

**Pattern: Integration test with live LLM (test_agent_v2.py):**
```python
def test_law_article_question():
    """Law article questions should return non-null answer with at most 2 pages."""
    qs = load_warmup()
    law_q = next(
        q for q in qs
        if "Article" in q.get("question", "") and "Employment" in q.get("question", "")
    )
    result = answer_question(law_q)
    assert result["answer"] is not None
    assert len(result["chunk_pages"]) >= 1
    total_pages = sum(len(c["page_numbers"]) for c in result["chunk_pages"])
    assert total_pages <= 2
```

## Mocking

**Framework:** None

**Patterns:**
- No mocking is used. Tests run against real data files in `data/` directory.
- Tests that require LLM calls (`test_agent_v2.py`) make actual API calls.
- Tests that require index data (`test_case_index.py`, `test_law_index_v2.py`) read real JSON files.

**What to Mock (if adding tests):**
- Anthropic API calls (to avoid cost/latency in CI)
- File I/O for PDF reading
- ChromaDB collection queries

**What NOT to Mock:**
- JSON index loading (tests validate real data structure)
- Regex patterns (deterministic, no external deps)

## Fixtures and Factories

**Test Data:**
- Tests load real data from `data/` directory:
  ```python
  def load_warmup():
      qs = json.load(open("data/public_dataset.json"))
      return qs["questions"] if isinstance(qs, dict) and "questions" in qs else qs
  ```
- No synthetic fixtures, factories, or `conftest.py` fixtures beyond sys.path setup

**Location:**
- Real data files in `data/`: `public_dataset.json`, `case_metadata_index.json`, `article_page_index.json`, `latest_edition_index.json`
- No dedicated fixtures directory

## Coverage

**Requirements:** None enforced. No coverage configuration.

**View Coverage:**
```bash
uv run pytest tests/ --cov=. --cov-report=term  # Would require pytest-cov (not installed)
```

## Test Types

**Unit Tests:**
- `tests/test_agent_tools.py` (81 lines, 8 tests): Tests individual helper functions (`search_within_doc`, `get_case_metadata`, `verify_page_supports_answer`, `get_latest_law_doc`) with real data files but no LLM calls
- Scope: function-level, validates return types and edge cases (None, empty, fake IDs)

**Data Validation Tests:**
- `tests/test_case_index.py` (19 lines, 2 tests): Validates `case_metadata_index.json` structure and content
- `tests/test_law_index_v2.py` (14 lines, 2 tests): Validates `latest_edition_index.json` structure and content
- Scope: Ensures data pipeline outputs are well-formed before the main pipeline runs

**Integration Tests:**
- `tests/test_agent_v2.py` (49 lines, 3 tests): End-to-end tests that call `answer_question()` with real questions from `data/public_dataset.json`
- These tests make live Anthropic API calls and require `ANTHROPIC_API_KEY`
- Written as "red-green" tests (designed to fail before implementation, pass after)

**E2E / Evaluation Tests:**
- No pytest-based E2E tests
- The primary evaluation loop is in `finals.py` itself, which processes all questions and outputs a JSON submission file
- Evaluation is done by submitting to the platform API and comparing scores

## Local Evaluation Methodology

**Primary evaluation flow:**
```bash
# 1. Run the full pipeline
uv run python finals.py --workers 5 --questions data/questions.json --output results/submission.json

# 2. Submit to platform for scoring (manual step, requires explicit user approval)
# Platform returns: S_det, S_asst, G, T, F scores
```

**Smoke testing (built into prepare_corpus.py):**
```bash
uv run python prepare_corpus.py --smoke-test-only  # Runs 10 questions through pipeline
```

**Regression approach:**
- No automated regression test suite
- Regression is tracked by platform submission scores (S_det, S_asst, G, T, F)
- Historical scores recorded in project memory files (not in code)
- The team relies on "targeted fixes only" philosophy: fix specific failing questions, never make blanket changes

## CI/CD Setup

**CI Pipeline:** None

- No `.github/workflows/` directory
- No CI configuration files detected
- No pre-commit hooks configured
- All testing is manual via local `uv run pytest` and platform submissions

**Deployment:**
- Manual submission to evaluation platform
- Results JSON files saved to local `results/` directory
- No automated deployment pipeline

## What IS Tested

- Helper function correctness (`search_within_doc`, `get_case_metadata`, etc.)
- Data index structure and completeness (case metadata, law index)
- Answer format types (boolean returns bool, confidence in [0,1])
- Edge cases: fake document IDs, missing cases, empty pages
- Page count constraints (max 2 pages per single-law question)

## What is NOT Tested

- `router.py` (1304 lines) -- deterministic routing with complex regex, no tests
- `retriever.py` (1606 lines) -- hybrid BM25+vector retrieval, no tests
- `answerer_v3.py` (2152 lines) -- LLM answer generation, no tests
- `finals.py` (1841 lines) -- main orchestrator, no tests
- `format_guardian.py` (655 lines) -- format validation/fixing, no tests
- `llm_reranker.py` (294 lines) -- LLM-based reranking, no tests
- `page_verifier.py` (489 lines) -- page verification logic, no tests
- `indexer.py` (358 lines) -- ChromaDB indexing, no tests
- Error handling paths (retry logic, timeout handling, fallback chains)
- Trick question detection logic in `finals.py` and `answerer_v3.py`
- Cross-encoder reranking correctness
- Thread safety of singleton initialization patterns

## Observations for Future Testing

1. **`format_guardian.py`** is the most testable untested module -- pure functions, no external deps, already has `FormatGuardian` class with clear input/output contracts
2. **`router.py`** regex patterns are deterministic and highly testable -- each `CASE_ID_PATTERN`, `ARTICLE_PATTERN`, etc. could have unit tests
3. **Trick question detection** (`_is_trick_question` in `finals.py`) is a pure function that would benefit from a truth table of known trick/non-trick questions
4. **Integration tests in `test_agent_v2.py`** import from `agent_v2` which does not exist in the current codebase (legacy import) -- these tests would fail with `ImportError`

---

*Testing analysis: 2026-03-23*
