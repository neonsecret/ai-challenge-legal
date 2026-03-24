# Legal RAG Bench: Adaptation Guide

## The Problem

Our retriever is indexed on DIFC documents. Legal RAG Bench uses 4,876 passages from
Victoria's Criminal Charge Book. The current `run.py` uses a naive keyword overlap
retriever (`_simple_retrieve`) -- far weaker than our actual pipeline capabilities.

## What Needs to Change

### Step 1: Download Corpus from HuggingFace

Already implemented in `run.py`:
```python
corpus_ds = hf_load("isaacus/legal-rag-bench", "corpus", split="test")
qa_ds = hf_load("isaacus/legal-rag-bench", "qa", split="test")
```

The corpus has 4,876 passages with fields: `id`, `title`, `text`, `footnotes`.

### Step 2: Build a FAISS Index from the Corpus Passages

```python
from sentence_transformers import SentenceTransformer
import faiss, json, numpy as np

model = SentenceTransformer("Snowflake/snowflake-arctic-embed-l-v2.0")

# Each passage is already a discrete retrieval unit (no chunking needed)
texts = [row["text"] for row in corpus_ds]
ids = [row["id"] for row in corpus_ds]

# Embed all passages
embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)

# Build FAISS index
index = faiss.IndexFlatIP(embeddings.shape[1])
index.add(embeddings.astype(np.float32))
faiss.write_index(index, "benchmarks/legal-rag-bench/data/faiss_index.bin")

# Save metadata
metadata = [{"id": pid, "text": t} for pid, t in zip(ids, texts)]
with open("benchmarks/legal-rag-bench/data/faiss_metadata.json", "w") as f:
    json.dump(metadata, f)
```

### Step 3: Build BM25 Index

```python
import bm25s
from arlc.indexing.legal_tokenizer import legal_tokenize_corpus

tokenized = legal_tokenize_corpus(texts)
bm25 = bm25s.BM25()
bm25.index(tokenized)
bm25.save("benchmarks/legal-rag-bench/data/bm25_cache")
```

### Step 4: Implement Hybrid Retrieval

Replace `_simple_retrieve()` with our actual hybrid approach:
1. BM25 search over the corpus
2. Vector search over the FAISS index
3. Cross-encoder reranking of merged candidates
4. Return top-k passage IDs

### Step 5: Generate Answers with Our Answerer

The existing `run_pipeline()` already calls `generate_answer`. Just need to feed
properly retrieved passages instead of keyword-matched ones.

## Leaderboard Context

### Published Results (March 2026)

| Embedding Model           | Gen Model      | Correctness | Retrieval Acc | Groundedness |
|--------------------------|----------------|-------------|---------------|--------------|
| Kanon 2 Embedder         | GPT-5.2        | 80.3%       | 94%           | High         |
| Kanon 2 Embedder         | Gemini 3.1 Pro | 79.3%       | 94%           | High         |
| Text Embedding 3 Large   | GPT-5.2        | ~63%        | 60%           | Baseline     |
| Text Embedding 3 Large   | Gemini 3.1 Pro | ~62%        | 60%           | Baseline     |
| Gemini Embedding 001     | GPT-5.2        | ~63%        | <60%          | Lower        |

Key findings:
- Retrieval is the bottleneck (not reasoning)
- Kanon 2 legal-domain embedder beats general-purpose by +34% retrieval accuracy
- Generative model choice only swings +/-3%
- Hallucination rate: Gemini 3.1 Pro 5.7%, GPT-5.2 11.3%

### Where We Would Rank

Our Snowflake Arctic Embed + BM25 + cross-encoder hybrid should compete with
general-purpose embedders (~60% retrieval accuracy). To beat Kanon 2 (94%) we would
need the cross-encoder reranking to significantly boost recall.

**Realistic estimate**: 65-75% retrieval accuracy (between general-purpose and Kanon 2).
End-to-end correctness depends heavily on retrieval quality.

## Estimated Effort

- **Index building**: ~30 min (4,876 passages is small)
- **Code changes**: Moderate -- FAISS index builder + hybrid retrieval adapter
- **Cost**: Embedding (free) + 100 LLM calls for answer generation (~$1-2)
