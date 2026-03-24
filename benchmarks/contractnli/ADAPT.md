# ContractNLI: Adaptation Guide

## The Problem

ContractNLI requires reading 607 NDAs and classifying 17 hypotheses per NDA as
Entailment/Contradiction/NotMentioned. Our pipeline is built for DIFC document QA,
not contract NLI classification. No corpus indexing is needed -- each NDA is provided
as the full document to classify against.

## What Works Already

1. Dataset downloads automatically (ZIP from Stanford NLP)
2. Each NDA text is fed directly to the answerer (no retrieval needed)
3. Classification logic frames NLI as a question to our LLM
4. Metrics computation (accuracy, macro F1, per-class, confusion matrix) is correct

## What Could Be Improved

### Better NLI Prompting

The current prompt is generic. For ContractNLI specifically:

```python
# Current (generic)
question = "Based on the following contract, classify the hypothesis as one of: ..."

# Improved (domain-specific)
question = (
    "You are a legal expert reviewing a Non-Disclosure Agreement (NDA). "
    "Determine the relationship between the NDA and the following hypothesis.\n\n"
    "Hypothesis: {hypothesis}\n\n"
    "Classify as:\n"
    "- Entailment: The NDA explicitly supports or implies this hypothesis\n"
    "- Contradiction: The NDA explicitly contradicts this hypothesis\n"
    "- NotMentioned: The NDA does not address this topic at all\n\n"
    "Respond with ONLY one word: Entailment, Contradiction, or NotMentioned."
)
```

### Full Document Handling

Current code truncates NDAs to 8000 chars. Most NDAs are longer. Options:
1. Increase to full document (Claude Sonnet handles 200K context)
2. Use our retriever to find relevant spans first, then classify
3. Chunk the NDA and classify each chunk, then aggregate

### Evidence Span Extraction

ContractNLI also evaluates evidence identification (which spans support the decision).
Current `run.py` does not extract evidence spans. Adding this would enable:
- Evidence F1 metric (mean average precision)
- More meaningful comparison with Span NLI BERT baseline

## Leaderboard Context

### Published Results (EMNLP 2021 + subsequent work)

**Span NLI BERT (original baseline):**

| Model Variant   | NLI Accuracy | Evidence mAP |
|----------------|-------------|-------------|
| BERT_base       | ~83%        | ~0.885       |
| BERT_large      | ~87.5%      | ~0.922       |
| DeBERTa v2_xlarge | ~89% (est) | ~0.93 (est)  |

**Classical baselines:**
- Majority class: ~45% accuracy
- TF-IDF + SVM: ~65% accuracy
- SQuAD-style QA: ~70% accuracy

**LLM-era estimates (no formal leaderboard):**
- GPT-4 zero-shot on contract NLI tasks: ~85-90% accuracy (various papers)
- Claude Sonnet with proper prompting: ~85-90% accuracy (estimated)
- Fine-tuned legal LLMs: ~90-92% accuracy (estimated from related benchmarks)

### Where We Would Rank

With Claude Sonnet as our backbone:
- **NLI Accuracy**: Likely 85-90% (competitive with BERT_large baseline)
- **Evidence identification**: Not currently implemented
- Zero-shot LLMs typically match or beat fine-tuned BERT on NLI tasks

Note: Papers with Code was shut down by Meta in July 2025. No actively maintained
public leaderboard exists for ContractNLI anymore.

## Estimated Effort

- **No indexing needed** -- documents provided directly
- **Code changes**: Minor -- improve prompt, remove truncation
- **Cost**: 607 NDAs x 17 hypotheses = 10,319 LLM calls (~$30-50 with Sonnet)
- **Full run time**: ~3-5 hours at normal rate limits
