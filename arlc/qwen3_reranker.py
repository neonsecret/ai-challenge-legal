"""Qwen3-Reranker inference via causal LM yes/no token probabilities.

Qwen3-Reranker models are generative (decoder-only) models that output "yes" or "no"
to judge document relevance. They CANNOT be used as sequence classifiers via
CrossEncoder — that would load a random score head and produce garbage scores.

This module provides a CrossEncoder-compatible predict() interface backed by
the correct causal LM inference path.

Usage:
    from arlc.qwen3_reranker import Qwen3Reranker
    reranker = Qwen3Reranker()
    scores = reranker.predict([("query", "document"), ...])  # returns numpy array
"""
from __future__ import annotations

import logging
import os
from typing import Optional, Union

import numpy as np
import torch

logger = logging.getLogger(__name__)

# System prompt used by all Qwen3-Reranker model variants
_SYSTEM_PROMPT = (
    'Judge whether the Document meets the requirements based on the Query and the Instruct. '
    'Note that the answer can only be "yes" or "no".'
)


class Qwen3Reranker:
    """Instruction-aware reranker using Qwen3-Reranker causal LM inference.

    Extracts the log-probability of the "yes" token at the final position as
    the relevance score — the correct approach for generative reranker models.

    Parameters
    ----------
    model_name:
        HuggingFace model ID. Defaults to Qwen/Qwen3-Reranker-0.6B.
    instruction:
        Task-level instruction injected into the prompt. Keep general so it
        works across customer domains.
    device:
        Torch device. Auto-detected (CUDA > MPS > CPU) if None.
    batch_size:
        Number of pairs processed per forward pass.
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-Reranker-0.6B",
        instruction: str = "Given a legal question, retrieve the most relevant passage that directly answers it.",
        device: Optional[str] = None,
        batch_size: int = 8,
    ) -> None:
        self.model_name = model_name
        self.instruction = instruction
        self.batch_size = batch_size

        if device is None:
            device = (
                "cuda" if torch.cuda.is_available()
                else "mps" if torch.backends.mps.is_available()
                else "cpu"
            )
        self.device = device

        from transformers import AutoTokenizer, AutoModelForCausalLM

        logger.info("Loading Qwen3-Reranker %s on %s", model_name, device)
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            padding_side="left",
            trust_remote_code=True,
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            dtype=torch.float16 if device in ("cuda", "mps") else torch.float32,
            trust_remote_code=True,
        ).to(device)
        self.model.eval()

        # Token IDs for "yes" and "no" in Qwen tokenizer
        self._yes_id = self.tokenizer.convert_tokens_to_ids("yes")
        self._no_id = self.tokenizer.convert_tokens_to_ids("no")
        logger.info(
            "Qwen3-Reranker loaded. yes_id=%d, no_id=%d", self._yes_id, self._no_id
        )

    def _make_prompt(self, query: str, document: str) -> str:
        """Build the full chat-template prompt for one (query, document) pair."""
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"<Instruct>: {self.instruction}\n"
                    f"<Query>: {query}\n"
                    f"<Document>: {document}"
                ),
            },
        ]
        return self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )

    def _score_batch(self, prompts: list[str]) -> list[float]:
        """Run one forward pass and return P(yes) for each prompt."""
        encoded = self.tokenizer(
            prompts,
            padding=True,
            truncation=True,
            max_length=2048,
            return_tensors="pt",
        )
        target = "cuda:0" if self.device == "cuda" else self.device
        encoded = {k: v.to(target) for k, v in encoded.items()}

        with torch.no_grad():
            logits = self.model(**encoded).logits  # (B, seq_len, vocab)

        # Score = log-softmax over (yes, no) at last token position
        last_logits = logits[:, -1, :]  # (B, vocab)
        yes_no = last_logits[:, [self._yes_id, self._no_id]]  # (B, 2)
        probs = torch.softmax(yes_no, dim=-1)[:, 0]  # P(yes), shape (B,)
        return probs.cpu().float().tolist()

    def predict(
        self,
        sentences: list[tuple[str, str]],
        batch_size: Optional[int] = None,
        **kwargs,
    ) -> np.ndarray:
        """Score (query, document) pairs. Returns float32 numpy array of relevance scores.

        Drop-in replacement for CrossEncoder.predict().
        """
        bs = batch_size or self.batch_size
        prompts = [self._make_prompt(q, doc) for q, doc in sentences]
        all_scores: list[float] = []
        for start in range(0, len(prompts), bs):
            batch = prompts[start: start + bs]
            all_scores.extend(self._score_batch(batch))
        return np.array(all_scores, dtype=np.float32)
