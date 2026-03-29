# RAGAS Evaluation

## What it tests

Drop-in evaluation framework that measures four core RAG quality dimensions:

- **Faithfulness**: Is the answer grounded in the retrieved context?
- **Answer Relevancy**: Does the answer address the question?
- **Context Precision**: Are retrieved contexts relevant to the question?
- **Context Recall**: Do retrieved contexts cover the ground truth answer?

## Setup

```bash
pip install -r requirements.txt
# Requires OPENAI_API_KEY in .env (RAGAS uses OpenAI for LLM-based metrics)
```

## Run

```bash
# From ARLC submission output:
python benchmarks/ragas/run.py --input output/submission.json

# Dry run (validate input format only):
python benchmarks/ragas/run.py --input output/submission.json --dry-run

# With limit:
python benchmarks/ragas/run.py --input output/submission.json --limit 10
```

## Input format

The script reads an ARLC submission JSON (or any JSON with the fields below)
and evaluates each entry:

```json
{
  "question": "...",
  "answer": "...",
  "contexts": ["retrieved page text 1", "..."],
  "ground_truth": "expected answer (optional)"
}
```

## Output

JSON at `benchmarks/ragas/results.json` with per-question and aggregate scores
for each RAGAS metric.
