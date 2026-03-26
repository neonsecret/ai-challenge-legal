"""NeoLex application settings.

Reads configuration from environment variables only.
LLM secrets (ANTHROPIC_API_KEY, proxy URLs) are NOT stored here —
they are read by arlc/ directly from .env via python-dotenv.

Environment variables:
    NEOLEX_WORKERS              Worker concurrency (default: 5)
    ALLOWED_ORIGINS             Comma-separated CORS origins (default: http://localhost:3000)
    NEOLEX_DB_PATH              SQLite audit DB path (default: neolex.db)
    NEOLEX_DATA_DIR             Data directory (default: data)
    REQUEST_TIMEOUT_SECONDS     Per-request timeout in seconds (default: 30)
    LOG_FORMAT                  "json" | "human" | auto-detect from TTY
    LOG_LEVEL                   Python log level (default: INFO)
"""
import os


class Settings:
    app_name: str = "NeoLex"
    app_version: str = "0.1.0"
    workers: int = int(os.environ.get("NEOLEX_WORKERS", "5"))
    # CORS — dev default allows Next.js dev server; locked in production via env var.
    # Tailscale Funnel URL should be added via ALLOWED_ORIGINS in production.
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.environ.get(
            "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000"
        ).split(",")
        if origin.strip()
    ]
    # SQLite audit DB path
    db_path: str = os.environ.get("NEOLEX_DB_PATH", "neolex.db")
    # Data directory for documents and client indexes
    data_dir: str = os.environ.get("NEOLEX_DATA_DIR", "data")
    # Per-request timeout (seconds). 0 disables the timeout.
    request_timeout_seconds: float = float(
        os.environ.get("REQUEST_TIMEOUT_SECONDS", "30")
    )
    # Demo mode — pre-seeds a demo API key, shows demo badge in frontend.
    demo_mode: bool = os.environ.get("DEMO_MODE", "").lower() in ("1", "true", "yes")


settings = Settings()
