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
	uv run python prepare_corpus.py

# Build indexes only (skip download)
index:
	uv run python build_case_metadata_auto.py
	uv run python build_law_index_v2.py
	uv run python build_article_index.py
	uv run python indexer.py

# Run the pipeline
run:
	uv run python finals.py --workers 5 --output output/run1
