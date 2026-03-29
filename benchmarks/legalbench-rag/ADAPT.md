# LegalBench-RAG: Adaptation Guide

## The Problem

Our pipeline indexes DIFC court documents. LegalBench-RAG has its own corpus of legal
contracts (ContractNLI NDAs, CUAD, MAUD M&A agreements, PrivacyQA). The current `run.py`
calls `arlc.retriever.retrieve()` which searches our DIFC FAISS index -- completely wrong
corpus.

## What Needs to Change

### Step 1: Download the LegalBench-RAG Corpus

The dataset auto-downloads from Dropbox (already implemented in `run.py`). After download:

- `data/corpus/` contains raw `.txt` files of legal contracts
- `data/benchmarks/` contains JSON files with queries + gold character spans

### Step 2: Build a FAISS Index from Their Corpus

We need to chunk and index the LegalBench-RAG corpus files using our indexing pipeline.

```python
# Pseudocode for adaptation
from arlc.indexing.indexer import clean_text_for_embedding
from sentence_transformers import SentenceTransformer
import faiss, json

model = SentenceTransformer("Snowflake/snowflake-arctic-embed-l-v2.0")

# 1. Read all corpus .txt files
# 2. Chunk with RCTS (recursive character text splitter), ~500 char chunks
# 3. Record file path + char start/end for each chunk
# 4. Embed all chunks with our Arctic model
# 5. Build FAISS index (IndexFlatIP for cosine similarity)
# 6. Save index + metadata mapping chunk_id -> {file, start, end, text}
```

Key parameters to match the benchmark's evaluation:

- **Chunking**: Use RCTS (best performer in paper) with ~500 char chunks
- **No reranker**: Paper found Cohere reranker HURTS legal retrieval
- **k=10**: Retrieve top 10 chunks per query (paper tests k=1 to k=64)

### Step 3: Update `run.py` to Use the New Index

Replace `retrieve_for_query()` to search the LegalBench-RAG-specific FAISS index
instead of calling `arlc.retriever.retrieve()`.

### Step 4: Run Character-Level Evaluation

The existing `compute_char_overlap()` function is correct. It computes character-level
precision/recall/F1 by comparing predicted spans against gold spans.

## Leaderboard Context

### Published Results (from paper, August 2024)

Best configuration: **RCTS + No Reranker** (Snowflake Arctic Embed)

| Dataset     | Precision@1 | Recall@64 |
|-------------|-------------|-----------|
| PrivacyQA   | 14.38%      | 84.19%    |
| ContractNLI | 6.63%       | 61.72%    |
| MAUD        | 2.65%       | 28.28%    |
| CUAD        | 1.97%       | 74.70%    |

Key findings:

- MAUD (M&A) is hardest -- highly technical domain
- Cohere reranker performs WORSE than no reranker on legal text
- Character-level metrics are very strict (partial overlap penalized)

### Where We Would Rank

No public leaderboard exists. The paper only tests one embedding model with two
chunking strategies and two reranker configs. Any system that beats RCTS+No Reranker
at k=10 would be SOTA on this benchmark.

Our hybrid BM25 + vector + cross-encoder approach should significantly outperform
the paper's single-signal retrieval, especially with legal-domain tuning.

## Estimated Effort

- **Index building**: 2-3 hours (corpus is ~79M characters)
- **Code changes**: Moderate -- need FAISS index builder + adapter in `run.py`
- **Cost**: Embedding only, no LLM calls for retrieval-only evaluation
