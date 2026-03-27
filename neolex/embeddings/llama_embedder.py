"""llama-server embedding client for Qwen3-Embedding GGUF models.

Replaces the PyTorch-based Qwen3Embedder with a thin HTTP client that talks to
a running llama-server instance.  Drop-in replacement: implements the same
embed_texts / embed_query / encode API.

Why llama.cpp over PyTorch:
  - Q4_K_M quantization: ~4.3 GB for 8B vs ~14 GB float16 — fits both
    Apple Silicon (Metal) and RTX 3070 (8 GB VRAM) with room to spare
  - Metal and CUDA paths are battle-tested in llama.cpp; MPS in PyTorch is
    still experimental for large decoder models
  - No torch dependency for inference

Starting the server
-------------------
Local (Apple Silicon, Metal):
    llama-server -m models/Qwen3-Embedding-8B-Q4_K_M.gguf \\
        --embedding --pooling last -ngl 99 -c 4096 --port 8088

Remote (RTX 3070, CUDA):
    ~/llama.cpp/build/bin/llama-server \\
        -m models/Qwen3-Embedding-8B-Q4_K_M.gguf \\
        --embedding --pooling last -ngl 99 -c 4096 --port 8088

Environment variables
---------------------
LLAMA_SERVER_URL   URL of the running server (default: http://localhost:8088)
LLAMA_MODEL_PATH   Path to .gguf file — used only by start_server()
LLAMA_N_GPU_LAYERS Number of layers to offload to GPU/Metal (default: 99)
"""
from __future__ import annotations

import logging
import os
import shutil
import signal
import socket
import subprocess
import time
from contextlib import contextmanager
from typing import Optional, Union

import numpy as np
import requests

logger = logging.getLogger(__name__)

# Task description shared with Qwen3Embedder so query prefixes are identical
QWEN_QUERY_TASK = "Given a legal document query, retrieve the most relevant passages"
QWEN_QUERY_PREFIX = f"Instruct: {QWEN_QUERY_TASK}\nQuery: "

_DEFAULT_URL = os.environ.get("LLAMA_SERVER_URL", "http://localhost:8088")


class LlamaServerEmbedder:
    """HTTP client for a llama-server /v1/embeddings endpoint.

    Assumes the server is already running with::

        llama-server -m <model.gguf> --embedding --pooling last -ngl 99

    Parameters
    ----------
    url:
        Base URL of the llama-server instance.
    batch_size:
        Number of texts sent per HTTP request.  The server processes them in
        parallel internally.  64 is a safe default; raise if GPU has headroom.
    """

    def __init__(self, url: str = _DEFAULT_URL, batch_size: int = 64) -> None:
        self.url = url.rstrip("/")
        self.batch_size = batch_size
        self._verify_server()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _verify_server(self) -> None:
        """Raise a clear error if the server is not reachable."""
        try:
            r = requests.get(f"{self.url}/health", timeout=10)
            r.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"llama-server not reachable at {self.url}.\n"
                f"Start it with:\n"
                f"  llama-server -m <model.gguf> --embedding --pooling last "
                f"-ngl 99 -c 4096 --port 8088\n"
                f"Or set LLAMA_SERVER_URL to the correct address."
            )
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"llama-server health check failed: {e}")

    def _embed_batch(self, texts: list[str]) -> np.ndarray:
        """POST a single batch to /v1/embeddings; returns (N, dim) float32."""
        r = requests.post(
            f"{self.url}/v1/embeddings",
            json={"input": texts, "encoding_format": "float"},
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()["data"]
        # API guarantees order == input order, but sort defensively
        data.sort(key=lambda x: x["index"])
        matrix = np.array([d["embedding"] for d in data], dtype=np.float32)
        # L2-normalise (llama-server doesn't always normalise for us)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms = np.where(norms == 0.0, 1.0, norms)
        return matrix / norms

    # ------------------------------------------------------------------
    # Public API — matches Qwen3Embedder
    # ------------------------------------------------------------------

    def embed_texts(
        self,
        texts: list[str],
        batch_size: Optional[int] = None,
        **kwargs,
    ) -> np.ndarray:
        """Embed document passages without an instruction prefix.

        Returns (N, dim) float32 numpy array, L2-normalised.
        """
        bs = batch_size or self.batch_size
        chunks = []
        for start in range(0, len(texts), bs):
            chunks.append(self._embed_batch(texts[start: start + bs]))
        return np.concatenate(chunks, axis=0)

    def embed_query(
        self,
        query: str,
        task: str = QWEN_QUERY_TASK,
    ) -> np.ndarray:
        """Embed a single query with the Qwen3 instruction prefix.

        Returns (dim,) float32 numpy array, L2-normalised.
        """
        prefixed = f"Instruct: {task}\nQuery: {query}"
        return self._embed_batch([prefixed])[0]

    def encode(
        self,
        sentences: Union[str, list[str]],
        normalize_embeddings: bool = True,
        prompt_name: Optional[str] = None,
        **kwargs,
    ) -> np.ndarray:
        """SentenceTransformer-compatible encode() API.

        When ``prompt_name='query'``, prepends the Qwen3 instruction prefix so
        that query/passage asymmetry is preserved.

        Returns (N, dim) or (dim,) float32 numpy array (already L2-normalised).
        """
        scalar = isinstance(sentences, str)
        if scalar:
            sentences = [sentences]
        if prompt_name == "query":
            sentences = [QWEN_QUERY_PREFIX + s for s in sentences]
        result = self.embed_texts(sentences)
        return result[0] if scalar else result


# ------------------------------------------------------------------
# Server lifecycle helpers
# ------------------------------------------------------------------

def _find_llama_server() -> str:
    """Return path to llama-server binary, searching common locations."""
    # Prefer the system PATH first (e.g. Homebrew on Mac)
    found = shutil.which("llama-server")
    if found:
        return found
    # Common build locations
    candidates = [
        os.path.expanduser("~/llama.cpp/build/bin/llama-server"),
        "/usr/local/bin/llama-server",
        "/opt/homebrew/bin/llama-server",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    raise FileNotFoundError(
        "llama-server not found. Install via 'brew install llama.cpp' or build from source."
    )


def _wait_for_port(host: str, port: int, timeout: float = 60.0) -> None:
    """Block until the TCP port is accepting connections."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(0.5)
    raise TimeoutError(f"llama-server did not start within {timeout:.0f}s on port {port}")


@contextmanager
def start_server(
    model_path: Optional[str] = None,
    port: int = 8088,
    n_gpu_layers: int = 99,
    context_size: int = 4096,
):
    """Context manager that starts a llama-server subprocess and yields its URL.

    Usage::

        with start_server("models/Qwen3-Embedding-8B-Q4_K_M.gguf") as url:
            embedder = LlamaServerEmbedder(url=url)
            embedder.embed_texts(...)

    If a server is already running on the port, skips launching a new one and
    yields the URL directly (safe for re-entrant use).
    """
    model_path = model_path or os.environ.get("LLAMA_MODEL_PATH")
    if not model_path:
        raise ValueError(
            "model_path is required. Pass it directly or set LLAMA_MODEL_PATH."
        )

    # Check if something is already on the port
    already_running = False
    try:
        with socket.create_connection(("localhost", port), timeout=1):
            already_running = True
    except OSError:
        pass

    if already_running:
        logger.info("llama-server already running on port %d, reusing.", port)
        yield f"http://localhost:{port}"
        return

    binary = _find_llama_server()
    cmd = [
        binary,
        "-m", model_path,
        "--embedding",
        "--pooling", "last",
        "-ngl", str(n_gpu_layers),
        "-c", str(context_size),
        "--port", str(port),
        "--host", "127.0.0.1",
        "--log-disable",  # suppress verbose output to stderr
    ]
    logger.info("Starting llama-server: %s", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_port("127.0.0.1", port, timeout=120)
        logger.info("llama-server ready on port %d (pid %d)", port, proc.pid)
        yield f"http://localhost:{port}"
    finally:
        logger.info("Shutting down llama-server (pid %d)", proc.pid)
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
