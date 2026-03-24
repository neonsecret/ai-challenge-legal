# RAGAS: Adaptation Guide

## The Problem (Non-Problem)

RAGAS is an evaluation framework, not a benchmark corpus. It measures the quality of
ANY RAG pipeline's output using LLM-as-judge metrics. Our current `run.py` already
works correctly -- it takes ARLC submission output and evaluates it with RAGAS metrics.

No corpus indexing is needed. RAGAS evaluates whatever output you feed it.

## What Works Already

1. Loads ARLC submission JSON (question + answer + contexts + ground_truth)
2. Runs four RAGAS metrics: Faithfulness, Answer Relevancy, Context Precision, Context Recall
3. Supports both modern RAGAS API (>=0.4.0) and legacy API
4. Outputs per-question and aggregate scores

## What Could Be Improved

### Use with Other Benchmark Outputs

RAGAS can be applied as a meta-evaluator on top of other benchmark runs:

```bash
# Evaluate Legal RAG Bench output with RAGAS
python benchmarks/ragas/run.py --input benchmarks/legal-rag-bench/results.json

# Evaluate GaRAGe output with RAGAS
python benchmarks/ragas/run.py --input benchmarks/garage/results.json
```

For this to work, the other benchmark `run.py` scripts need to save output in
RAGAS-compatible format: `{question, answer, contexts, ground_truth}`.

### Anthropic Backend Instead of OpenAI

RAGAS defaults to OpenAI for its LLM-as-judge evaluations. To use Anthropic:

```python
from ragas.llms import LangchainLLMWrapper
from langchain_anthropic import ChatAnthropic

llm = LangchainLLMWrapper(ChatAnthropic(model="claude-sonnet-4-20250514"))
# Pass llm= to each metric
```

### Reference-Free Evaluation

For benchmarks without ground truth answers, use reference-free metrics only:
- Faithfulness (does answer match retrieved context?)
- Answer Relevancy (does answer address the question?)
- Context Precision (are retrieved passages relevant?)

## Leaderboard Context

### No Standard Leaderboard

RAGAS is a framework, not a competition. There is no single leaderboard. However,
typical score ranges from published papers:

| Metric              | Poor   | Average | Good   | Excellent |
|--------------------|--------|---------|--------|-----------|
| Faithfulness        | <0.5   | 0.5-0.7 | 0.7-0.85 | >0.85   |
| Answer Relevancy    | <0.5   | 0.5-0.7 | 0.7-0.85 | >0.85   |
| Context Precision   | <0.3   | 0.3-0.6 | 0.6-0.8  | >0.8    |
| Context Recall      | <0.3   | 0.3-0.6 | 0.6-0.8  | >0.8    |

These ranges are approximate and vary significantly by domain and task difficulty.
Legal domain typically scores lower than general domain due to terminology precision.

### How Our Pipeline Would Score

Based on our ARLC competition results (S_asst=0.761, G=0.797):
- **Faithfulness**: Likely 0.75-0.85 (our answers are well-grounded)
- **Answer Relevancy**: Likely 0.70-0.80 (calibration phrases may reduce this)
- **Context Precision**: Likely 0.60-0.75 (depends on retrieval quality)
- **Context Recall**: Likely 0.55-0.70 (single page per doc limits coverage)

## Estimated Effort

- **No indexing needed** -- evaluates existing output
- **Code changes**: None needed for basic usage
- **Cost**: RAGAS uses LLM-as-judge, ~2x the number of samples in LLM calls
- **Prerequisite**: Need OPENAI_API_KEY (or adapt to use Anthropic)
