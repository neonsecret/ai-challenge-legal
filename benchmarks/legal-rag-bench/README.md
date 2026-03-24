# Legal RAG Bench

## What it tests
End-to-end RAG performance on 100 expert-written criminal law questions from the
Victorian Judicial College Criminal Charge Book. Evaluates retrieval accuracy
(correct passage ID), answer correctness (semantic similarity to gold answer),
and answer groundedness (answer supported by retrieved context).

## Dataset
- **Source**: HuggingFace `isaacus/legal-rag-bench`
- **Corpus**: 4,876 passages (id, title, text, footnotes)
- **QA**: 100 questions with expert answers and relevant_passage_id

## Setup
```bash
pip install -r requirements.txt
```

## Run
```bash
# 1. Download dataset and build indexes (required before first run):
python benchmarks/legal-rag-bench/run.py --dry-run
python benchmarks/legal-rag-bench/build_index.py

# 2. Quick test:
python benchmarks/legal-rag-bench/run.py --limit 5

# 3. Full evaluation:
python benchmarks/legal-rag-bench/run.py
```

## Output
JSON at `benchmarks/legal-rag-bench/results.json` with retrieval_accuracy,
answer_similarity (ROUGE-L), and groundedness metrics.
