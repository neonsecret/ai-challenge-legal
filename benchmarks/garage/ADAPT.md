# GaRAGe: Adaptation Guide

## The Problem (Non-Problem)

GaRAGe provides passages WITH each question -- no corpus indexing needed. The benchmark
tests grounding/attribution quality, not retrieval. Our current `run.py` already works
correctly: it feeds the provided passages to our answerer and evaluates grounding.

## What Works Already

1. Dataset downloads from GitHub (JSONL format)
2. Passages are provided per-question (no retrieval step)
3. Our answerer generates answers from the provided passages
4. Grounding evaluation compares against gold relevance labels

## What Could Be Improved

### Better Grounding Evaluation

The current `evaluate_grounding()` uses a simple word-overlap heuristic to check
if the answer references each passage. This should be replaced with the paper's
official evaluation method:

1. Use GPT-4o as judge (temperature=0.2) to evaluate:
   - **Factuality**: Is the answer factually correct given the passages?
   - **Attribution**: Does the answer properly cite/ground in relevant passages?
   - **Deflection**: Does the model correctly abstain when no relevant passage exists?

2. Compute the paper's official metrics:
   - **RAF (Relevance-Aware Factuality)**: Factuality weighted by passage relevance
   - **Deflection TPR**: True positive rate for abstention
   - **Attribution F1**: Precision/recall of passage-level attribution

### Passage Format Alignment

The current code treats all passages as strings. The actual dataset has structured
fields per passage that should be preserved.

## Leaderboard Context

### Published Results (ACL 2025)

**Relevance-Aware Factuality (RAF):**

| Model         | Eligibility | Factuality | RAF    |
|--------------|-------------|-----------|--------|
| Nova Pro      | 87.77%      | 66.63%    | 60.67% |
| Gemini 1.5    | 84.88%      | 70.50%    | 59.43% |
| GPT-4o        | 92.47%      | 59.30%    | 52.88% |
| Qwen 32b      | 90.50%      | 61.00%    | 52.90% |
| Claude Sonnet  | 86.07%      | 64.67%    | 48.91% |
| Claude Haiku   | 79.37%      | 48.37%    | 36.90% |
| Mistral        | 85.30%      | 43.32%    | 34.32% |

**Deflection (ability to abstain when no relevant passage):**

| Model         | TPR    | FPR   |
|--------------|--------|-------|
| GPT-4o        | 31.1%  | 2.3%  |
| Gemini 1.5    | 27.2%  | 2.3%  |
| Claude Sonnet  | 25.3%  | 1.4%  |
| Qwen 32b      | 21.5%  | 1.2%  |

**Attribution F1:**

| Model         | Precision | Recall | F1    |
|--------------|-----------|--------|-------|
| Claude Haiku   | 49.9%     | 71.9%  | 58.9% |
| GPT-4o        | 57.9%     | 59.0%  | 58.4% |
| Claude Sonnet  | 51.8%     | 67.5%  | 58.6% |
| Gemini 1.5    | 54.7%     | 56.3%  | 55.5% |

### Where We Would Rank

Our pipeline uses Claude Sonnet for answering. Based on the published results:
- **RAF**: ~49% (Claude Sonnet baseline), could improve with better prompting
- **Attribution F1**: ~58.6% (already near SOTA -- all models cluster at 50-59%)
- **Deflection**: ~25% TPR (our absence detection could help here)

The benchmark shows ALL models struggle -- best RAF is only 60.67%. This is a hard
benchmark where even SOTA systems fail 40%+ of the time.

## Estimated Effort

- **No indexing needed** -- passages provided per question
- **Code changes**: Minor -- improve evaluation metrics to match paper's methodology
- **Cost**: ~2,366 LLM calls for full evaluation (~$10-20 with Sonnet)
