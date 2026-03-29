# GaRAGe Benchmark

## What it tests

Grounding and citation accuracy. The benchmark provides 2,366 questions with 35K+
passage-level relevance and grounding annotations. Each passage is labeled as
relevant (YES/NO) and categorized (ANSWER-THE-QUESTION / RELATED-INFORMATION / UNKNOWN).

Tests whether our pipeline can correctly identify which passages ground an answer
and whether generated answers are faithful to retrieved context.

## Dataset

- **Source**: https://github.com/amazon-science/GaRAGe
- **Format**: JSONL with 21 fields per entry
- **License**: CC-BY-NC-4.0

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
# Dry run:
python benchmarks/garage/run.py --dry-run

# Quick test:
python benchmarks/garage/run.py --limit 10

# Full run:
python benchmarks/garage/run.py
```

## Output

JSON at `benchmarks/garage/results.json` with passage-level grounding precision/recall
and answer faithfulness metrics.
