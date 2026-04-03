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

import enum
import logging
import os
import shutil
import signal
import socket
import subprocess
import threading
import time
from contextlib import contextmanager
from typing import Optional, Union

import numpy as np
import requests

logger = logging.getLogger(__name__)

# Task description for query instruction prefix.
# Domain-specific instructions significantly outperform generic ones on legal retrieval.
# Override via LLAMA_QUERY_TASK env var for different domains.
QWEN_QUERY_TASK = os.environ.get(
    "LLAMA_QUERY_TASK",
    "Given a legal question, find the relevant legal provision, court judgment, or statutory rule",
)
QWEN_QUERY_PREFIX = f"Instruct: {QWEN_QUERY_TASK}\nQuery: "

_DEFAULT_URL = os.environ.get("LLAMA_SERVER_URL", "http://localhost:8088")
_REMOTE_URL = os.environ.get("LLAMA_SERVER_REMOTE_URL", "http://100.98.171.97:8088")
_HEALTH_CHECK_INTERVAL = 30  # seconds between remote health checks

# Circuit breaker defaults for the local embedding server
_CB_THRESHOLD = int(os.environ.get("EMBED_CB_THRESHOLD", "3"))  # consecutive failures to OPEN
_CB_COOLDOWN = float(os.environ.get("EMBED_CB_COOLDOWN", "30"))  # seconds before HALF-OPEN probe


class _CBState(enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class EmbeddingServerUnavailableError(RuntimeError):
    """Raised when the local embedding server circuit breaker is OPEN.

    The circuit opens after ``EMBED_CB_THRESHOLD`` consecutive failures and
    remains open for ``EMBED_CB_COOLDOWN`` seconds before allowing a probe.
    This prevents cascading 120-second TCP timeouts when llama-server:8088
    goes offline.
    """


class LlamaServerEmbedder:
    """HTTP client for a llama-server /v1/embeddings endpoint.

    Supports automatic failover: if LLAMA_SERVER_REMOTE_URL is set and healthy,
    it's used as primary (RTX 3070 CUDA >> local MPS).  Falls back to the local
    server on any error.  Health is re-checked periodically.

    Circuit breaker for the local server prevents cascading TCP timeouts when
    llama-server:8088 goes offline.  After ``EMBED_CB_THRESHOLD`` consecutive
    failures the circuit OPENS and requests fail fast with
    ``EmbeddingServerUnavailableError``.  After ``EMBED_CB_COOLDOWN`` seconds a
    single probe is allowed (HALF-OPEN); success closes the circuit and triggers
    a remote-server re-check for possible auto-promotion.

    Parameters
    ----------
    url:
        Base URL of the local llama-server instance (fallback).
    batch_size:
        Number of texts sent per HTTP request.
    """

    def __init__(self, url: str = _DEFAULT_URL, batch_size: int = 64) -> None:
        self._local_url = url.rstrip("/")
        self._remote_url = _REMOTE_URL.rstrip("/") if _REMOTE_URL else ""
        self._remote_healthy = False
        self._last_health_check = 0.0
        self._health_lock = threading.Lock()  # prevents concurrent health checks
        self.batch_size = batch_size

        # Circuit breaker state for the local embedding server
        self._cb_state = _CBState.CLOSED
        self._cb_fail_count = 0
        self._cb_open_at = 0.0
        self._cb_lock = threading.Lock()

        # Verify at least the local server is reachable
        self._verify_server_url(self._local_url)

        # Check if remote is available (non-blocking, best-effort)
        if self._remote_url and self._remote_url != self._local_url:
            self._check_remote_health()
            if self._remote_healthy:
                logger.info("Remote llama-server at %s is healthy — using as primary", self._remote_url)
            else:
                logger.info("Remote llama-server at %s is offline — using local only", self._remote_url)

            # Background daemon thread: polls remote health and auto-promotes on recovery.
            # Runs independently of embedding requests — catches recovery even during idle periods.
            self._start_health_poll_thread()

    @property
    def url(self) -> str:
        """Active server URL — remote if healthy, local otherwise."""
        if self._remote_url and self._remote_url != self._local_url:
            now = time.monotonic()
            if now - self._last_health_check > _HEALTH_CHECK_INTERVAL:
                self._check_remote_health()
            if self._remote_healthy:
                return self._remote_url
        return self._local_url

    def _check_remote_health(self) -> None:
        """Quick health check on the remote server (non-blocking lock prevents concurrent checks)."""
        if not self._health_lock.acquire(blocking=False):
            return  # another thread is already checking; skip to avoid duplicate HTTP requests
        try:
            self._last_health_check = time.monotonic()
            try:
                r = requests.get(f"{self._remote_url}/health", timeout=3)
                self._remote_healthy = r.ok
            except Exception:
                self._remote_healthy = False
        finally:
            self._health_lock.release()

    # ------------------------------------------------------------------
    # Circuit breaker — local embedding server
    # ------------------------------------------------------------------

    @property
    def circuit_state(self) -> _CBState:
        """Current circuit breaker state (CLOSED / OPEN / HALF_OPEN)."""
        with self._cb_lock:
            return self._cb_state

    def _cb_allow_request(self) -> bool:
        """Return True if a request to the local server should proceed.

        Transitions OPEN → HALF_OPEN once the cooldown elapses so that a
        single probe can test whether the server has recovered.
        """
        with self._cb_lock:
            if self._cb_state == _CBState.CLOSED:
                return True
            if self._cb_state == _CBState.OPEN:
                if time.monotonic() - self._cb_open_at >= _CB_COOLDOWN:
                    self._cb_state = _CBState.HALF_OPEN
                    logger.info(
                        "Embedding circuit breaker HALF-OPEN — probing %s",
                        self._local_url,
                    )
                    return True
                return False  # still within cooldown: fast-fail
            # HALF_OPEN: allow the probe through
            return True

    def _cb_record_success(self) -> None:
        """Record a successful local request; close circuit and trigger remote re-check."""
        trigger_recheck = False
        with self._cb_lock:
            if self._cb_state in (_CBState.HALF_OPEN, _CBState.OPEN):
                logger.info(
                    "Embedding circuit breaker CLOSED — %s recovered",
                    self._local_url,
                )
                self._cb_state = _CBState.CLOSED
                self._cb_fail_count = 0
                trigger_recheck = bool(self._remote_url and self._remote_url != self._local_url)
            else:
                # Reset consecutive-failure counter on any success in CLOSED state
                self._cb_fail_count = 0
        if trigger_recheck:
            # Re-check remote health outside the lock so auto-promotion can proceed
            threading.Thread(
                target=self._check_remote_health,
                daemon=True,
                name="embed-remote-recheck",
            ).start()

    def _cb_record_failure(self) -> None:
        """Record a failed local request; trip circuit after threshold."""
        with self._cb_lock:
            if self._cb_state == _CBState.HALF_OPEN:
                self._cb_state = _CBState.OPEN
                self._cb_open_at = time.monotonic()
                logger.warning(
                    "Embedding circuit breaker OPEN again — probe failed for %s",
                    self._local_url,
                )
            elif self._cb_state == _CBState.CLOSED:
                self._cb_fail_count += 1
                if self._cb_fail_count >= _CB_THRESHOLD:
                    self._cb_state = _CBState.OPEN
                    self._cb_open_at = time.monotonic()
                    logger.warning(
                        "Embedding circuit breaker OPENED after %d consecutive failures for %s",
                        self._cb_fail_count,
                        self._local_url,
                    )

    def _start_health_poll_thread(self) -> None:
        """Start a daemon thread that polls remote health and auto-promotes on recovery."""
        t = threading.Thread(
            target=self._health_poll_loop,
            daemon=True,
            name="embed-health-poll",
        )
        t.start()
        logger.debug(
            "Embedding health poller started for %s (interval=%ds)",
            self._remote_url,
            _HEALTH_CHECK_INTERVAL,
        )

    def _health_poll_loop(self) -> None:
        """Background loop: poll remote server health every interval, log state transitions."""
        while True:
            time.sleep(_HEALTH_CHECK_INTERVAL)
            was_healthy = self._remote_healthy
            self._check_remote_health()
            now_healthy = self._remote_healthy
            if not was_healthy and now_healthy:
                logger.info(
                    "Embedding server %s recovered — auto-promoting to primary",
                    self._remote_url,
                )
            elif was_healthy and not now_healthy:
                logger.warning(
                    "Embedding server %s went offline — falling back to local (%s)",
                    self._remote_url,
                    self._local_url,
                )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _verify_server_url(url: str) -> None:
        """Raise a clear error if the server is not reachable."""
        try:
            r = requests.get(f"{url}/health", timeout=10)
            r.raise_for_status()
        except requests.exceptions.ConnectionError as err:
            raise RuntimeError(
                f"llama-server not reachable at {url}.\n"
                f"Start it with:\n"
                f"  llama-server -m <model.gguf> --embedding --pooling last "
                f"-ngl 99 -c 4096 --port 8088\n"
                f"Or set LLAMA_SERVER_URL to the correct address.",
            ) from err
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"llama-server health check failed: {e}") from e

    def _embed_batch(self, texts: list[str]) -> np.ndarray:
        """POST a single batch to /v1/embeddings; returns (N, dim) float32.

        Uses the active server (remote if healthy, else local).  On remote
        failure, falls back to local.  The local server is protected by a
        circuit breaker: when OPEN, raises ``EmbeddingServerUnavailableError``
        immediately rather than waiting for a TCP timeout.
        """
        active_url = self.url  # property: remote if healthy, else local

        if active_url == self._local_url:
            # Local is primary — check circuit breaker before attempting
            if not self._cb_allow_request():
                raise EmbeddingServerUnavailableError(
                    f"Embedding server {self._local_url} unavailable "
                    f"(circuit OPEN, retry after {_CB_COOLDOWN:.0f}s cooldown)"
                )
            try:
                result = self._embed_batch_url(active_url, texts)
                self._cb_record_success()
                return result
            except EmbeddingServerUnavailableError:
                raise
            except Exception:
                self._cb_record_failure()
                raise

        # Remote is primary — attempt it, fall back to local on any error
        try:
            return self._embed_batch_url(active_url, texts)
        except Exception:
            logger.warning("Remote embedding failed, falling back to local")
            self._remote_healthy = False
            if not self._cb_allow_request():
                raise EmbeddingServerUnavailableError(
                    f"Embedding server {self._local_url} unavailable "
                    f"(circuit OPEN, retry after {_CB_COOLDOWN:.0f}s cooldown)"
                )
            try:
                result = self._embed_batch_url(self._local_url, texts)
                self._cb_record_success()
                return result
            except EmbeddingServerUnavailableError:
                raise
            except Exception:
                self._cb_record_failure()
                raise

    @staticmethod
    def _embed_batch_url(url: str, texts: list[str]) -> np.ndarray:
        """POST a batch to a specific server URL."""
        r = requests.post(
            f"{url}/v1/embeddings",
            json={"input": texts, "encoding_format": "float"},
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()["data"]
        data.sort(key=lambda x: x["index"])
        matrix = np.array([d["embedding"] for d in data], dtype=np.float32)
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
            chunks.append(self._embed_batch(texts[start : start + bs]))
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
    raise FileNotFoundError("llama-server not found. Install via 'brew install llama.cpp' or build from source.")


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
        raise ValueError("model_path is required. Pass it directly or set LLAMA_MODEL_PATH.")

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
        "-m",
        model_path,
        "--embedding",
        "--pooling",
        "last",
        "-ngl",
        str(n_gpu_layers),
        "-c",
        str(context_size),
        "--port",
        str(port),
        "--host",
        "127.0.0.1",
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
