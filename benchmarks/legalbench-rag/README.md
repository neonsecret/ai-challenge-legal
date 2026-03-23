# LegalBench-RAG Benchmark

## What it tests
Character-level retrieval precision and recall on legal contracts. The corpus contains
raw text files from ContractNLI, CUAD, MAUD, and PrivacyQA. Ground-truth annotations
specify exact character ranges within those files.

## Setup
```bash
pip install -r requirements.txt
# Dataset is auto-downloaded from the LegalBench-RAG Dropbox on first run.
```

## Run
```bash
# Dry run (download data only, no LLM calls):
python benchmarks/legalbench-rag/run.py --dry-run

# Quick test with 5 queries:
python benchmarks/legalbench-rag/run.py --limit 5

# Full evaluation:
python benchmarks/legalbench-rag/run.py
```

## Output
JSON file at `benchmarks/legalbench-rag/results.json` with per-query and aggregate
precision / recall / F1 at character level.
