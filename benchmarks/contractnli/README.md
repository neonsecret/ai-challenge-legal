# ContractNLI Benchmark

## What it tests

Natural Language Inference on 607 non-disclosure agreements. For each NDA and
each of 17 fixed hypotheses, the model must classify the relationship as:

- **Entailment**: the NDA supports the hypothesis
- **Contradiction**: the NDA contradicts the hypothesis
- **NotMentioned**: the hypothesis is not addressed

Tests our pipeline's ability to perform boolean/classification QA on legal contracts.

## Dataset

- **Source**: https://stanfordnlp.github.io/contract-nli/
- **Size**: 607 NDAs, 17 hypotheses each = 10,319 classification instances
- **License**: CC BY 4.0

## Setup

```bash
pip install -r requirements.txt
# Dataset auto-downloaded on first run
```

## Run

```bash
# Dry run:
python benchmarks/contractnli/run.py --dry-run

# Quick test:
python benchmarks/contractnli/run.py --limit 5

# Full run:
python benchmarks/contractnli/run.py
```

## Output

JSON at `benchmarks/contractnli/results.json` with per-hypothesis and overall
accuracy, macro F1, and confusion matrix.
