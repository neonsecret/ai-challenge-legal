"""NeoLex application settings.

Reads configuration from environment variables only.
LLM secrets (ANTHROPIC_API_KEY, proxy URLs) are NOT stored here —
they are read by arlc/ directly from .env via python-dotenv.
"""
import os


class Settings:
    app_name: str = "NeoLex"
    app_version: str = "0.1.0"
    workers: int = int(os.environ.get("NEOLEX_WORKERS", "5"))
    # CORS — dev default allows Next.js dev server; locked in production via env var
    cors_origins: list[str] = os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:3000"
    ).split(",")
    # SQLite audit DB path (Phase 2 will use this)
    db_path: str = os.environ.get("NEOLEX_DB_PATH", "neolex.db")


settings = Settings()
