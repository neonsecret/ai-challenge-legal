"""Lightweight reranker server for remote GPU inference.

Deploy on RTX 3070 (or any CUDA machine):

    pip install fastapi uvicorn transformers torch
    CUDA_VISIBLE_DEVICES=0 uvicorn scripts.reranker_server:app --host 0.0.0.0 --port 8089

The Mac backend connects to this via RERANKER_SERVER_URL=http://100.98.171.97:8089
"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Qwen3-Reranker Service")

# Lazy-loaded model
_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        from arlc.qwen3_reranker import Qwen3Reranker

        _reranker = Qwen3Reranker(
            model_name="Qwen/Qwen3-Reranker-0.6B",
            instruction="Given a legal question, retrieve the most relevant passage that directly answers it.",
            device="cuda",  # Force CUDA on RTX 3070
            batch_size=64,  # CUDA handles larger batches easily
        )
    return _reranker


class Pair(BaseModel):
    query: str
    document: str


class RerankRequest(BaseModel):
    pairs: list[Pair]
    timeout: float | None = None


class RerankResponse(BaseModel):
    scores: list[float]
    elapsed_ms: float


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/rerank", response_model=RerankResponse)
async def rerank(body: RerankRequest):
    t0 = time.monotonic()
    ranker = _get_reranker()
    sentences = [(p.query, p.document) for p in body.pairs]
    scores = ranker.predict(sentences, timeout=body.timeout)
    elapsed = (time.monotonic() - t0) * 1000
    logger.info("Reranked %d pairs in %.0fms", len(sentences), elapsed)
    return RerankResponse(scores=scores.tolist(), elapsed_ms=elapsed)
