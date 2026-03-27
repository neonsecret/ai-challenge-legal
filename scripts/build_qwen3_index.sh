#!/usr/bin/env bash
# Build a FAISS index using Qwen3-8B embeddings.
#
# Reads all chunk JSON files from data/chunks/ and writes:
#   data/faiss_qwen3_8b.bin   — FAISS flat IP index
#   data/faiss_qwen3_8b.json  — chunk metadata (doc_id, page, text preview)
#
# Run on the remote GPU machine (RTX 3070, 8 GB VRAM):
#   ssh neon@100.98.171.97
#   cd ~/ai-challenge-legal-new
#   bash scripts/build_qwen3_index.sh
#
# Override model or output path:
#   EMBEDDING_MODEL=qwen3-0.6b OUTPUT=data/faiss_qwen3_06b.bin bash scripts/build_qwen3_index.sh
#
set -euo pipefail

EMBEDDING_MODEL="${EMBEDDING_MODEL:-qwen3-8b}"
EMBEDDING_DIM="${EMBEDDING_DIM:-1024}"
CORPUS="${CORPUS:-data/chunks/}"
OUTPUT="${OUTPUT:-data/faiss_qwen3_8b.bin}"

echo "=== Qwen3 FAISS Index Builder ==="
echo "  EMBEDDING_MODEL : ${EMBEDDING_MODEL}"
echo "  EMBEDDING_DIM   : ${EMBEDDING_DIM}"
echo "  CORPUS          : ${CORPUS}"
echo "  OUTPUT          : ${OUTPUT}"
echo ""

# Prefer the conda env python if available (remote GPU machine)
PYTHON="${PYTHON:-$(command -v python3)}"
if [[ -x "$HOME/.conda/envs/torch313/bin/python3" ]]; then
    PYTHON="$HOME/.conda/envs/torch313/bin/python3"
fi

echo "Using Python: ${PYTHON}"
echo ""

EMBEDDING_MODEL="${EMBEDDING_MODEL}" \
EMBEDDING_DIM="${EMBEDDING_DIM}" \
"${PYTHON}" -m neolex.embeddings.build_index \
    --corpus "${CORPUS}" \
    --output "${OUTPUT}"

echo ""
echo "Done. Index written to: ${OUTPUT}"
