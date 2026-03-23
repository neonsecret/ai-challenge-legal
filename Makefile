.PHONY: setup lint test run index prepare

# Install dependencies
setup:
	uv sync

# Lint with ruff
lint:
	uv run ruff check .

# Run tests
test:
	uv run pytest tests/ -v

# Prepare corpus (download + index)
prepare:
	uv run python -m arlc.indexing.prepare_corpus

# Build indexes only (skip download)
index:
	uv run python -m arlc.indexing.builders.case_metadata
	uv run python -m arlc.indexing.builders.law_index
	uv run python -m arlc.indexing.builders.article_index
	uv run python -m arlc.indexing.indexer

# Run the pipeline
run:
	uv run python run.py --workers 5 --output output/run1
