"""NeoLex structured logging configuration.

Uses stdlib logging only (no new dependencies).

Two formats:
- JSON (production): machine-readable, one JSON object per line.
  Enabled when LOG_FORMAT=json or LOG_FORMAT is unset and not a TTY.
- Human (development): coloured, readable.
  Enabled when LOG_FORMAT=human or running on a TTY (interactive terminal).

Request IDs are included automatically when present in the log record's
``extra`` dict (set by RequestIDMiddleware and explicit logger calls).

Usage:
    from neolex.logging_config import configure_logging
    configure_logging()   # call once at startup, before any loggers are used
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects.

    Standard fields: ts, level, logger, message, request_id (when present).
    Extra fields passed via ``extra=`` in logger calls are included at the
    top level (not nested).
    """

    # Fields that are always part of logging.LogRecord — we do NOT want them
    # duplicated in the JSON output as extra fields.
    _SKIP_ATTRS = frozenset({
        "args", "created", "exc_info", "exc_text", "filename", "funcName",
        "levelname", "levelno", "lineno", "message", "module", "msecs",
        "msg", "name", "pathname", "process", "processName", "relativeCreated",
        "stack_info", "thread", "threadName", "taskName",
    })

    def format(self, record: logging.LogRecord) -> str:
        # Build the core payload.
        payload: dict = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include exception info if present.
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Include any extra fields set via logger.info("...", extra={...}).
        for key, value in record.__dict__.items():
            if key not in self._SKIP_ATTRS and not key.startswith("_"):
                payload[key] = value

        return json.dumps(payload, default=str)


# ---------------------------------------------------------------------------
# Human formatter (dev)
# ---------------------------------------------------------------------------

class HumanFormatter(logging.Formatter):
    """Coloured, human-readable formatter for development."""

    _COLORS = {
        "DEBUG":    "\033[36m",   # cyan
        "INFO":     "\033[32m",   # green
        "WARNING":  "\033[33m",   # yellow
        "ERROR":    "\033[31m",   # red
        "CRITICAL": "\033[35m",   # magenta
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelname, "")
        reset = self._RESET
        ts = self.formatTime(record, datefmt="%H:%M:%S")
        msg = record.getMessage()

        # Append request_id if present.
        request_id = record.__dict__.get("request_id", "")
        rid_suffix = f" [{request_id[:8]}]" if request_id else ""

        base = f"{ts} {color}{record.levelname:8}{reset} {record.name}: {msg}{rid_suffix}"

        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)

        return base


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _should_use_json() -> bool:
    fmt = os.environ.get("LOG_FORMAT", "").lower()
    if fmt == "json":
        return True
    if fmt == "human":
        return False
    # Auto-detect: use JSON when stdout is not a TTY (e.g. in production/docker).
    return not sys.stdout.isatty()


def configure_logging(level: str | None = None) -> None:
    """Configure root logger and silence noisy third-party loggers.

    Call once at application startup (main.py does this before importing
    routers).  Subsequent calls are idempotent (the handler is not added
    twice thanks to the `force=False` guard).
    """
    log_level = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()

    formatter: logging.Formatter
    if _should_use_json():
        formatter = JSONFormatter()
    else:
        formatter = HumanFormatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure the root logger.
    root = logging.getLogger()
    # Avoid adding the same handler multiple times (e.g. pytest re-runs).
    if not any(isinstance(h, logging.StreamHandler) and h.stream is sys.stdout
               for h in root.handlers):
        root.addHandler(handler)
    root.setLevel(log_level)

    # Silence noisy third-party loggers at WARNING level unless LOG_LEVEL=DEBUG.
    _noisy = [
        "httpx", "httpcore", "urllib3", "sentence_transformers",
        "faiss", "transformers", "torch", "filelock",
        "arlc",  # keep arlc quiet by default; it's very verbose
    ]
    if log_level != "DEBUG":
        for name in _noisy:
            logging.getLogger(name).setLevel(logging.WARNING)
