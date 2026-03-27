#!/usr/bin/env python3
"""
Fine-tune an embedding model on legal text using LoRA + sentence-transformers.

Strategy:
1. Generate synthetic (query, passage) pairs from the Legal RAG Bench corpus
   using a local LLM (via Ollama or direct model call)
2. Mine hard negatives using sentence-transformers mine_hard_negatives()
3. Fine-tune with CachedMultipleNegativesRankingLoss + MatryoshkaLoss + LoRA
4. Evaluate on Legal RAG Bench retrieval accuracy

RTX 3070 (8GB VRAM) feasibility:
- Qwen3-Embedding-0.6B: full fine-tune fits in ~4GB, LoRA fits in ~2.5GB
- Qwen3-Embedding-4B:   LoRA + 4-bit quant fits in ~6-7GB (use QLoRA)
- Qwen3-Embedding-8B:   does NOT fit in 8GB even with QLoRA (needs ~12GB)

Usage:
    # Step 1: Generate synthetic training data from corpus
    python scripts/finetune_legal_embedder.py --mode generate \
        --model Qwen/Qwen3-Embedding-0.6B \
        --output-dir outputs/finetune_06b

    # Step 2: Fine-tune
    python scripts/finetune_legal_embedder.py --mode train \
        --base-model Qwen/Qwen3-Embedding-0.6B \
        --data-dir outputs/finetune_06b \
        --output-dir outputs/finetune_06b \
        --lora-r 32 --lora-alpha 64 \
        --epochs 3 --batch-size 32

    # Step 3: Evaluate
    python scripts/finetune_legal_embedder.py --mode eval \
        --adapter-path outputs/finetune_06b/final_adapter \
        --base-model Qwen/Qwen3-Embedding-0.6B
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# STEP 1: Synthetic data generation
# ---------------------------------------------------------------------------

GENERATION_PROMPT = """\
You are a legal researcher. Given the following passage from an Australian criminal law \
charge book, generate {n} realistic questions that:
1. Can be answered using ONLY this passage
2. Vary in specificity (some factual, some conceptual, some definitional)
3. Use legal terminology naturally
4. Are phrased as a lawyer or judge might phrase them

Passage:
{passage}

Output ONLY the questions, one per line, no numbering, no preamble."""


def generate_synthetic_pairs(
    corpus_path: str | None,
    output_dir: Path,
    n_questions_per_passage: int = 3,
    max_passages: int = 2000,
    generator_model: str = "claude-sonnet-4-6",
) -> Path:
    """Generate (query, passage) positive pairs from corpus using an LLM.

    Uses Anthropic API by default. Falls back to a local template-based
    generator if ANTHROPIC_API_KEY is not set.
    """
    from datasets import load_dataset as hf_load

    output_dir.mkdir(parents=True, exist_ok=True)
    pairs_path = output_dir / "synthetic_pairs.jsonl"

    if pairs_path.exists():
        count = sum(1 for _ in open(pairs_path))
        print(f"[generate] Using existing {pairs_path} ({count} pairs)")
        return pairs_path

    print("[generate] Loading corpus from HuggingFace isaacus/legal-rag-bench...")
    corpus_ds = hf_load("isaacus/legal-rag-bench", "corpus", split="test")
    passages = [{"id": row["id"], "text": row["text"]} for row in corpus_ds]
    passages = passages[:max_passages]
    print(f"[generate] Processing {len(passages)} passages, {n_questions_per_passage} Q each "
          f"= ~{len(passages) * n_questions_per_passage} pairs target")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    use_llm = api_key is not None
    if not use_llm:
        print("[generate] WARNING: No ANTHROPIC_API_KEY. Using template-based generator.")

    pairs = []
    with open(pairs_path, "w") as f:
        for i, passage in enumerate(passages):
            text = passage["text"]
            pid = passage["id"]

            if use_llm:
                questions = _generate_with_anthropic(
                    text, n_questions_per_passage, generator_model, api_key
                )
            else:
                questions = _generate_template_questions(text, n_questions_per_passage)

            for q in questions:
                q = q.strip()
                if len(q) < 15:
                    continue
                pair = {"query": q, "positive": text, "passage_id": pid}
                f.write(json.dumps(pair) + "\n")
                pairs.append(pair)

            if (i + 1) % 100 == 0:
                print(f"  [{i+1}/{len(passages)}] Generated {len(pairs)} pairs so far")

    print(f"[generate] Done. {len(pairs)} pairs saved to {pairs_path}")
    return pairs_path


def _generate_with_anthropic(
    text: str, n: int, model: str, api_key: str
) -> list[str]:
    """Generate questions using the Anthropic API."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    prompt = GENERATION_PROMPT.format(n=n, passage=text[:3000])

    try:
        message = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text
        return [line.strip() for line in raw.split("\n") if line.strip()][:n]
    except Exception as e:
        print(f"  WARNING: API error: {e}")
        return _generate_template_questions(text, n)


def _generate_template_questions(text: str, n: int) -> list[str]:
    """Fallback: simple template questions when no LLM is available."""
    # Extract key legal terms and first sentence
    first_sentence = text.split(".")[0].strip()[:200]
    templates = [
        f"What does the law state about {first_sentence.lower()[:80]}?",
        f"What are the legal requirements described in this passage?",
        f"What elements must be established according to this passage?",
        f"How does Australian law define the concepts in this passage?",
        f"What standard of proof applies according to this passage?",
    ]
    return templates[:n]


# ---------------------------------------------------------------------------
# STEP 2: Hard negative mining
# ---------------------------------------------------------------------------

def mine_hard_negatives_for_dataset(
    pairs_path: Path,
    output_dir: Path,
    base_model: str,
    n_negatives: int = 1,
    cross_encoder_model: str | None = "BAAI/bge-reranker-v2-m3",
) -> Path:
    """Add hard negatives to training pairs using sentence-transformers v3.1+."""
    from datasets import Dataset
    from sentence_transformers import SentenceTransformer
    from sentence_transformers.util import mine_hard_negatives

    triplets_path = output_dir / "training_triplets.jsonl"
    if triplets_path.exists():
        count = sum(1 for _ in open(triplets_path))
        print(f"[mine] Using existing {triplets_path} ({count} triplets)")
        return triplets_path

    print(f"[mine] Loading pairs from {pairs_path}...")
    pairs = [json.loads(l) for l in open(pairs_path)]
    dataset = Dataset.from_dict({
        "anchor": [p["query"] for p in pairs],
        "positive": [p["positive"] for p in pairs],
    })

    print(f"[mine] Loading base model {base_model} for negative mining...")
    model = SentenceTransformer(base_model, trust_remote_code=True)

    print(f"[mine] Mining {n_negatives} hard negative(s) per pair...")
    # mine_hard_negatives is available in sentence-transformers >= 3.1.0
    # It uses FAISS internally to find near-misses from the positive pool
    mined = mine_hard_negatives(
        dataset=dataset,
        model=model,
        num_negatives=n_negatives,
        # cross_encoder_model=cross_encoder_model,  # optional — higher quality
        # margin=0.1,    # skip candidates within 0.1 of true positive similarity
        # max_score=0.9, # skip candidates with similarity > 0.9 (too similar = leakage)
        # range_min=10,  # skip the top-10 closest (likely positive)
        # range_max=100, # only consider top-100
        output_format="triplet",  # returns anchor, positive, negative columns
        batch_size=128,
        faiss_batch_size=65536,
    )
    print(f"[mine] Mined {len(mined)} triplets")

    with open(triplets_path, "w") as f:
        for row in mined:
            f.write(json.dumps({
                "anchor": row["anchor"],
                "positive": row["positive"],
                "negative": row["negative"],
            }) + "\n")

    print(f"[mine] Triplets saved to {triplets_path}")
    return triplets_path


# ---------------------------------------------------------------------------
# STEP 3: LoRA fine-tuning
# ---------------------------------------------------------------------------

def train(
    base_model: str,
    triplets_path: Path,
    output_dir: Path,
    # LoRA config
    lora_r: int = 32,
    lora_alpha: int = 64,
    lora_dropout: float = 0.05,
    # Training config
    epochs: int = 3,
    batch_size: int = 32,          # effective batch; CachedMNRL handles memory
    mini_batch_size: int = 16,     # actual GPU batch for gradient caching
    learning_rate: float = 2e-4,
    warmup_ratio: float = 0.1,
    # Matryoshka dims (set to None to disable MRL)
    matryoshka_dims: list[int] | None = None,  # e.g. [1024, 512, 256, 128, 64]
    use_fp16: bool = True,
    eval_steps: int = 100,
):
    """Full LoRA fine-tuning pipeline with CachedMultipleNegativesRankingLoss + MRL."""
    import torch
    from datasets import Dataset
    from peft import LoraConfig, TaskType
    from sentence_transformers import (
        SentenceTransformer,
        SentenceTransformerTrainer,
        SentenceTransformerTrainingArguments,
    )
    from sentence_transformers.losses import (
        CachedMultipleNegativesRankingLoss,
        MatryoshkaLoss,
    )
    from sentence_transformers.training_args import BatchSamplers
    from sentence_transformers.evaluation import InformationRetrievalEvaluator

    output_dir.mkdir(parents=True, exist_ok=True)

    # ---- Load model ----
    print(f"[train] Loading base model: {base_model}")
    model = SentenceTransformer(base_model, trust_remote_code=True)
    dim = model.get_sentence_embedding_dimension()
    print(f"[train] Embedding dimension: {dim}")

    # ---- Apply LoRA adapter ----
    # For Qwen3-Embedding (decoder-only LLM used as encoder), target attention layers.
    # Qwen3 architecture: q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj
    # For embedding quality, q/k/v/o are the most impactful; add gate/up/down for more capacity.
    peft_config = LoraConfig(
        task_type=TaskType.FEATURE_EXTRACTION,
        inference_mode=False,
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        # Target attention + some MLP layers for richer adaptation
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        bias="none",
    )
    model.add_adapter(peft_config)
    adapter_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"[train] Trainable params: {adapter_params/1e6:.2f}M / {total_params/1e6:.0f}M total "
          f"({100*adapter_params/total_params:.1f}%)")

    # ---- Load dataset ----
    print(f"[train] Loading triplets from {triplets_path}...")
    triplets = [json.loads(l) for l in open(triplets_path)]
    # 90/10 train/eval split
    split = int(len(triplets) * 0.9)
    train_data = triplets[:split]
    eval_data = triplets[split:]

    # Qwen3-Embedding requires instruction prefix on the query (anchor) side.
    # Documents (positive/negative) must NOT have the prefix.
    # Without this, the model's instruction-awareness is degraded during fine-tuning.
    QWEN3_QUERY_PREFIX = "Instruct: Retrieve the most relevant legal passage for the question\nQuery: "
    is_qwen3 = "qwen3" in base_model.lower()

    def maybe_prefix(query: str) -> str:
        return QWEN3_QUERY_PREFIX + query if is_qwen3 else query

    train_dataset = Dataset.from_dict({
        "anchor": [maybe_prefix(t["anchor"]) for t in train_data],
        "positive": [t["positive"] for t in train_data],
        "negative": [t["negative"] for t in train_data],
    })
    eval_dataset = Dataset.from_dict({
        "anchor": [maybe_prefix(t["anchor"]) for t in eval_data],
        "positive": [t["positive"] for t in eval_data],
        "negative": [t["negative"] for t in eval_data],
    })
    print(f"[train] Train: {len(train_dataset)} | Eval: {len(eval_dataset)}")

    # ---- Loss function ----
    # CachedMultipleNegativesRankingLoss = GradCache version of MNR loss.
    # Allows large effective batch sizes (good for in-batch negatives quality)
    # without proportional VRAM increase.
    # 2x slower than vanilla MNR but enables batch_size=256+ on 8GB GPU.
    base_loss = CachedMultipleNegativesRankingLoss(
        model,
        mini_batch_size=mini_batch_size,  # actual GPU micro-batch
        # show_progress_bar=False,
    )

    if matryoshka_dims is not None:
        # Matryoshka: train all dimensions simultaneously
        # dims must be <= model embedding dim and in descending order
        valid_dims = [d for d in sorted(matryoshka_dims, reverse=True) if d <= dim]
        loss = MatryoshkaLoss(
            model=model,
            loss=base_loss,
            matryoshka_dims=valid_dims,
        )
        print(f"[train] Using MatryoshkaLoss with dims: {valid_dims}")
    else:
        loss = base_loss
        print("[train] Using CachedMultipleNegativesRankingLoss (no Matryoshka)")

    # ---- Training arguments ----
    # NOTE: with CachedMNRL, per_device_train_batch_size is the full logical batch.
    # The mini_batch_size controls actual GPU memory. Use NO_DUPLICATES to avoid
    # anchor == negative collisions from in-batch negatives.
    args = SentenceTransformerTrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=learning_rate,
        warmup_ratio=warmup_ratio,
        fp16=use_fp16 and torch.cuda.is_available(),
        bf16=False,
        batch_sampler=BatchSamplers.NO_DUPLICATES,
        eval_strategy="steps",
        eval_steps=eval_steps,
        save_strategy="steps",
        save_steps=eval_steps,
        save_total_limit=2,
        logging_steps=50,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        # Gradient accumulation: helpful if batch_size > 32 causes OOM
        gradient_accumulation_steps=1,
        # Gradient checkpointing reduces VRAM at cost of ~20% speed
        # gradient_checkpointing=True,
        run_name=f"legal-embedder-lora-r{lora_r}",
        report_to=["none"],
    )

    # ---- Evaluator (optional: InformationRetrievalEvaluator on Legal RAG Bench) ----
    evaluator = None
    try:
        from datasets import load_dataset as hf_load
        qa_ds = hf_load("isaacus/legal-rag-bench", "qa", split="test")
        corpus_ds = hf_load("isaacus/legal-rag-bench", "corpus", split="test")
        # Build IR evaluator from first 50 questions
        queries = {str(i): row["question"] for i, row in enumerate(qa_ds)}
        corpus = {row["id"]: row["text"] for row in corpus_ds}
        relevant = {str(i): {row["relevant_passage_id"]} for i, row in enumerate(qa_ds)}
        evaluator = InformationRetrievalEvaluator(
            queries=queries,
            corpus=corpus,
            relevant_docs=relevant,
            name="legal-rag-bench",
            batch_size=32,
            show_progress_bar=False,
        )
        print("[train] InformationRetrievalEvaluator configured on Legal RAG Bench")
    except Exception as e:
        print(f"[train] Could not set up IR evaluator: {e}")

    # ---- Train ----
    trainer = SentenceTransformerTrainer(
        model=model,
        args=args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        loss=loss,
        evaluator=evaluator,
    )

    print("[train] Starting training...")
    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0
    print(f"[train] Training complete in {elapsed/60:.1f} minutes")

    # ---- Save adapter only (small: just LoRA weights) ----
    adapter_path = output_dir / "final_adapter"
    model.save_pretrained(str(adapter_path))
    print(f"[train] Adapter saved to {adapter_path}")

    # ---- Save merged model for inference (optional) ----
    merged_path = output_dir / "final_merged"
    try:
        # merge_adapter() collapses LoRA into base weights — needed for inference
        # without PEFT overhead
        merged_model = model
        merged_model[0].auto_model = merged_model[0].auto_model.merge_and_unload()
        merged_model.save_pretrained(str(merged_path))
        print(f"[train] Merged model saved to {merged_path}")
    except Exception as e:
        print(f"[train] Could not merge adapter: {e}. Use adapter_path for inference.")

    return adapter_path


# ---------------------------------------------------------------------------
# STEP 4: Evaluate fine-tuned model on Legal RAG Bench
# ---------------------------------------------------------------------------

def evaluate(
    base_model: str,
    adapter_path: str | None = None,
    merged_path: str | None = None,
    limit: int = 100,
):
    """Quick eval: retrieval accuracy @1, @3, @5, @10 on Legal RAG Bench."""
    import numpy as np
    from datasets import load_dataset as hf_load
    from sentence_transformers import SentenceTransformer

    if merged_path and Path(merged_path).exists():
        print(f"[eval] Loading merged model from {merged_path}")
        model = SentenceTransformer(merged_path, trust_remote_code=True)
    elif adapter_path and Path(adapter_path).exists():
        print(f"[eval] Loading base {base_model} + adapter {adapter_path}")
        model = SentenceTransformer(base_model, trust_remote_code=True)
        model.load_adapter(adapter_path)
    else:
        print(f"[eval] No adapter found, evaluating base model {base_model}")
        model = SentenceTransformer(base_model, trust_remote_code=True)

    print("[eval] Loading corpus...")
    corpus_ds = hf_load("isaacus/legal-rag-bench", "corpus", split="test")
    ids = [row["id"] for row in corpus_ds]
    texts = [row["text"] for row in corpus_ds]

    print(f"[eval] Embedding {len(texts)} corpus passages...")
    t0 = time.time()
    try:
        corpus_embs = model.encode(
            texts, prompt_name="passage",
            normalize_embeddings=True, batch_size=64, show_progress_bar=True
        )
    except Exception:
        corpus_embs = model.encode(
            texts, normalize_embeddings=True, batch_size=64, show_progress_bar=True
        )
    print(f"[eval] Corpus embedded in {time.time()-t0:.1f}s")

    print("[eval] Loading QA dataset...")
    qa_ds = hf_load("isaacus/legal-rag-bench", "qa", split="test")
    questions = list(qa_ds)[:limit]

    print(f"[eval] Evaluating {len(questions)} questions...")
    hits = {1: 0, 3: 0, 5: 0, 10: 0}
    for item in questions:
        q = item["question"]
        gold = item["relevant_passage_id"]

        try:
            q_emb = model.encode(q, prompt_name="query", normalize_embeddings=True)
        except Exception:
            q_emb = model.encode(q, normalize_embeddings=True)

        # Cosine similarity (embeddings already normalized)
        sims = corpus_embs @ q_emb
        top_indices = np.argsort(-sims)[:10]
        top_ids = [ids[i] for i in top_indices]

        for k in [1, 3, 5, 10]:
            if gold in top_ids[:k]:
                hits[k] += 1

    n = len(questions)
    print(f"\n{'='*50}")
    print(f"Model: {merged_path or adapter_path or base_model}")
    for k in [1, 3, 5, 10]:
        print(f"  Acc@{k:2d}: {hits[k]/n:.4f} ({hits[k]}/{n})")
    print(f"{'='*50}")

    return {k: hits[k] / n for k in [1, 3, 5, 10]}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fine-tune legal embedding model with LoRA")
    parser.add_argument("--mode", choices=["generate", "mine", "train", "eval", "full"],
                        default="full", help="Which step to run")
    parser.add_argument("--base-model", default="Qwen/Qwen3-Embedding-0.6B",
                        help="HuggingFace base embedding model")
    parser.add_argument("--output-dir", default="outputs/legal_embedder_lora",
                        help="Output directory for data and models")
    parser.add_argument("--data-dir", default=None,
                        help="Data directory (default: same as output-dir)")
    parser.add_argument("--adapter-path", default=None,
                        help="Path to fine-tuned adapter (for eval mode)")
    parser.add_argument("--merged-path", default=None,
                        help="Path to merged model (for eval mode)")

    # Data generation
    parser.add_argument("--n-questions", type=int, default=3,
                        help="Questions per passage for synthetic data generation")
    parser.add_argument("--max-passages", type=int, default=2000,
                        help="Max corpus passages to use for training data")
    parser.add_argument("--generator-model", default="claude-sonnet-4-6",
                        help="Anthropic model for synthetic data generation")

    # LoRA
    parser.add_argument("--lora-r", type=int, default=32, help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int, default=64, help="LoRA alpha")
    parser.add_argument("--lora-dropout", type=float, default=0.05)

    # Training
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=32,
                        help="Logical batch size (CachedMNRL handles GPU memory)")
    parser.add_argument("--mini-batch-size", type=int, default=16,
                        help="Actual GPU mini-batch for gradient caching")
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--no-matryoshka", action="store_true",
                        help="Disable Matryoshka loss (train full dim only)")

    # Eval
    parser.add_argument("--eval-limit", type=int, default=100)

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    data_dir = Path(args.data_dir) if args.data_dir else output_dir

    # Matryoshka dims: auto-detect from model or use defaults
    # Will be filtered to valid dims at training time
    matryoshka_dims = None if args.no_matryoshka else [1024, 512, 256, 128, 64]

    if args.mode in ("generate", "full"):
        pairs_path = generate_synthetic_pairs(
            corpus_path=None,
            output_dir=data_dir,
            n_questions_per_passage=args.n_questions,
            max_passages=args.max_passages,
            generator_model=args.generator_model,
        )

    if args.mode in ("mine", "full"):
        pairs_path = data_dir / "synthetic_pairs.jsonl"
        triplets_path = mine_hard_negatives_for_dataset(
            pairs_path=pairs_path,
            output_dir=data_dir,
            base_model=args.base_model,
        )

    if args.mode in ("train", "full"):
        triplets_path = data_dir / "training_triplets.jsonl"
        adapter_path = train(
            base_model=args.base_model,
            triplets_path=triplets_path,
            output_dir=output_dir,
            lora_r=args.lora_r,
            lora_alpha=args.lora_alpha,
            lora_dropout=args.lora_dropout,
            epochs=args.epochs,
            batch_size=args.batch_size,
            mini_batch_size=args.mini_batch_size,
            learning_rate=args.lr,
            matryoshka_dims=matryoshka_dims,
        )

    if args.mode in ("eval", "full"):
        evaluate(
            base_model=args.base_model,
            adapter_path=args.adapter_path or str(output_dir / "final_adapter"),
            merged_path=args.merged_path or str(output_dir / "final_merged"),
            limit=args.eval_limit,
        )


if __name__ == "__main__":
    main()
