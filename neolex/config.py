"""Vitreon Legal application settings.

Reads configuration from environment variables only.
LLM secrets (ANTHROPIC_API_KEY, proxy URLs) are NOT stored here —
they are read by arlc/ directly from .env via python-dotenv.

Environment variables:
    NEOLEX_WORKERS              Worker concurrency (default: 5)
    ALLOWED_ORIGINS             Comma-separated CORS origins (default: http://localhost:3000)
    NEOLEX_DATA_DIR             Data directory (default: data)
    REQUEST_TIMEOUT_SECONDS     Per-request timeout in seconds (default: 30)
    QUERY_PIPELINE_TIMEOUT_SECONDS  Internal timeout for /api/v1/query handler (default: 90)
    LOG_FORMAT                  "json" | "human" | auto-detect from TTY
    LOG_LEVEL                   Python log level (default: INFO)
    DATABASE_URL                PostgreSQL async URL (postgresql+asyncpg://...)
    GOOGLE_CLIENT_ID            Google OAuth client ID
    GOOGLE_CLIENT_SECRET        Google OAuth client secret
    JWT_SECRET_KEY              Secret for signing session state (openssl rand -base64 32)
    SESSION_COOKIE_NAME         Session cookie name (default: vitreon_session)
    SESSION_TTL_DAYS            Session lifetime in days (default: 30)
    AUTH_ENABLED                Enable auth middleware (default: false)
    RESEND_API_KEY              Resend transactional email API key
    EMAIL_FROM                  Sender address (default: noreply@vitreon.app)
    FREE_DAILY_LIMIT            Daily query limit for free tier (default: 10)
    STARTER_DAILY_LIMIT         Daily query limit for Starter plan (default: 30)
    STARTER_MAX_CORPORA         Max corpus uploads for Starter (default: 1)
    PRO_DAILY_LIMIT             Daily query limit for Pro plan (default: 200)
    PRO_MAX_CORPORA             Max corpus uploads for Pro (default: 3)
    ENTERPRISE_DAILY_LIMIT      Daily query limit for Enterprise (0=unlimited)
    ENTERPRISE_MAX_CORPORA      Max corpus uploads for Enterprise (default: 10)
    STARTER_MAX_DOCS_PER_CORPUS Max docs per corpus for Starter (default: 50)
    STARTER_MAX_CORPUS_SIZE_MB  Max corpus size in MB for Starter (default: 500)
    PRO_MAX_DOCS_PER_CORPUS     Max docs per corpus for Pro (default: 200)
    PRO_MAX_CORPUS_SIZE_MB      Max corpus size in MB for Pro (default: 2000)
    ENTERPRISE_MAX_DOCS_PER_CORPUS Max docs per corpus for Enterprise (default: 1000)
    ENTERPRISE_MAX_CORPUS_SIZE_MB  Max corpus size in MB for Enterprise (default: 10000)
    STRIPE_SECRET_KEY           Stripe secret key
    STRIPE_WEBHOOK_SECRET       Stripe webhook signing secret
    STRIPE_PRICE_*_MONTHLY      Stripe Price IDs for monthly billing
    STRIPE_PRICE_*_BIWEEKLY     Stripe Price IDs for biweekly billing
    STRIPE_ENABLED              Enable Stripe billing (default: false)
    FRONTEND_URL                Frontend base URL (default: http://localhost:3000)
    BACKEND_URL                 Backend base URL for email links (default: http://localhost:8000)
    DEV_MODE                    Disable secure cookies for local dev (default: false)
    LANGFUSE_ENABLED            Enable Langfuse observability (default: false)
    LANGFUSE_PUBLIC_KEY         Langfuse project public key
    LANGFUSE_SECRET_KEY         Langfuse project secret key
    LANGFUSE_HOST               Langfuse server URL (default: http://localhost:3040)
    RAGAS_SAMPLE_RATE           Fraction of queries scored by async RAGAS eval (0.0–1.0, default: 1.0)
"""

import os


class Settings:
    app_name: str = "Vitreon Legal"
    app_version: str = "0.1.0"
    workers: int = int(os.environ.get("NEOLEX_WORKERS", "5"))
    # CORS — dev default allows Next.js dev server; locked in production via env var.
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
        if origin.strip()
    ]
    # Data directory for documents and client indexes
    data_dir: str = os.environ.get("NEOLEX_DATA_DIR", "data")
    # Per-request timeout (seconds) for the global middleware. 0 disables it.
    request_timeout_seconds: float = float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "30"))
    # Internal timeout for the non-streaming /api/v1/query pipeline handler.
    # Longer than the middleware default because LLM generation can exceed 30s
    # on local hardware when the remote GPU node is offline.
    query_pipeline_timeout_seconds: float = float(os.environ.get("QUERY_PIPELINE_TIMEOUT_SECONDS", "90"))

    # --- PostgreSQL (auth + billing tables) ---
    database_url: str = os.environ.get("DATABASE_URL", "")

    # --- Auth ---
    google_client_id: str = os.environ.get("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    jwt_secret_key: str = os.environ.get("JWT_SECRET_KEY", "")
    session_cookie_name: str = os.environ.get("SESSION_COOKIE_NAME", "vitreon_session")
    session_ttl_days: int = int(os.environ.get("SESSION_TTL_DAYS", "30"))
    auth_enabled: bool = os.environ.get("AUTH_ENABLED", "").lower() in ("1", "true", "yes")

    # --- Email ---
    resend_api_key: str = os.environ.get("RESEND_API_KEY", "")
    email_from: str = os.environ.get("EMAIL_FROM", "noreply@vitreon.app")

    # --- Subscription plan limits ---
    # Pricing based on Sonnet 4.6: $3/$15 per M tokens, avg $0.044/query, worst $0.165/query
    # Free: loss leader. Starter: break-even ~22 queries/day. Pro: break-even ~75/day.
    free_daily_limit: int = int(os.environ.get("FREE_DAILY_LIMIT", "10"))
    starter_daily_limit: int = int(os.environ.get("STARTER_DAILY_LIMIT", "30"))
    starter_max_corpora: int = int(os.environ.get("STARTER_MAX_CORPORA", "1"))
    pro_daily_limit: int = int(os.environ.get("PRO_DAILY_LIMIT", "200"))
    pro_max_corpora: int = int(os.environ.get("PRO_MAX_CORPORA", "3"))
    # Enterprise daily limit: 0 is the sentinel for "unlimited" (no cap enforced).
    # This convention is relied upon by UNLIMITED_DAILY_QUERIES in neolex.routers.query.
    enterprise_daily_limit: int = int(os.environ.get("ENTERPRISE_DAILY_LIMIT", "0"))
    enterprise_max_corpora: int = int(os.environ.get("ENTERPRISE_MAX_CORPORA", "10"))

    # --- Per-corpus document/size limits ---
    starter_max_docs_per_corpus: int = int(os.environ.get("STARTER_MAX_DOCS_PER_CORPUS", "50"))
    starter_max_corpus_size_mb: int = int(os.environ.get("STARTER_MAX_CORPUS_SIZE_MB", "500"))
    pro_max_docs_per_corpus: int = int(os.environ.get("PRO_MAX_DOCS_PER_CORPUS", "200"))
    pro_max_corpus_size_mb: int = int(os.environ.get("PRO_MAX_CORPUS_SIZE_MB", "2000"))
    enterprise_max_docs_per_corpus: int = int(os.environ.get("ENTERPRISE_MAX_DOCS_PER_CORPUS", "1000"))
    enterprise_max_corpus_size_mb: int = int(os.environ.get("ENTERPRISE_MAX_CORPUS_SIZE_MB", "10000"))

    # --- Stripe ---
    # STRIPE_MODE: "test" (default) or "live". When "live", uses STRIPE_LIVE_SECRET_KEY instead.
    stripe_mode: str = os.environ.get("STRIPE_MODE", "test")

    @property
    def stripe_secret_key(self) -> str:
        if self.stripe_mode == "live":
            return os.environ.get("STRIPE_LIVE_SECRET_KEY", "")
        return os.environ.get("STRIPE_SECRET_KEY", "")

    @property
    def stripe_publishable_key(self) -> str:
        if self.stripe_mode == "live":
            return os.environ.get("STRIPE_LIVE_PUBLISHABLE_KEY", "")
        return os.environ.get("STRIPE_PUBLISHABLE_KEY", "")

    @property
    def stripe_webhook_secret(self) -> str:
        if self.stripe_mode == "live":
            return os.environ.get("STRIPE_LIVE_WEBHOOK_SECRET", "")
        return os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    stripe_enabled: bool = os.environ.get("STRIPE_ENABLED", "").lower() in ("1", "true", "yes")

    # --- Stripe Price IDs (per plan + interval) ---
    # Automatically selects live or test price IDs based on STRIPE_MODE.
    @property
    def stripe_price_starter_monthly(self) -> str:
        if self.stripe_mode == "live":
            return os.environ.get("STRIPE_LIVE_PRICE_STARTER_MONTHLY", "")
        return os.environ.get("STRIPE_PRICE_STARTER_MONTHLY", "")

    @property
    def stripe_price_pro_monthly(self) -> str:
        if self.stripe_mode == "live":
            return os.environ.get("STRIPE_LIVE_PRICE_PRO_MONTHLY", "")
        return os.environ.get("STRIPE_PRICE_PRO_MONTHLY", "")

    @property
    def stripe_price_enterprise_monthly(self) -> str:
        if self.stripe_mode == "live":
            return os.environ.get("STRIPE_LIVE_PRICE_ENTERPRISE_MONTHLY", "")
        return os.environ.get("STRIPE_PRICE_ENTERPRISE_MONTHLY", "")

    stripe_price_starter_biweekly: str = os.environ.get("STRIPE_PRICE_STARTER_BIWEEKLY", "")
    stripe_price_pro_biweekly: str = os.environ.get("STRIPE_PRICE_PRO_BIWEEKLY", "")
    stripe_price_enterprise_biweekly: str = os.environ.get("STRIPE_PRICE_ENTERPRISE_BIWEEKLY", "")

    # --- URLs ---
    frontend_url: str = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    backend_url: str = os.environ.get("BACKEND_URL", "http://localhost:8000")

    # --- Dev mode (disables Secure flag on cookies for local http) ---
    dev_mode: bool = os.environ.get("DEV_MODE", "false").lower() in ("1", "true", "yes")

    # --- Langfuse observability ---
    langfuse_enabled: bool = os.environ.get("LANGFUSE_ENABLED", "").lower() in ("1", "true", "yes")
    langfuse_public_key: str = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    langfuse_secret_key: str = os.environ.get("LANGFUSE_SECRET_KEY", "")
    langfuse_host: str = os.environ.get("LANGFUSE_HOST", "http://localhost:3040")

    # --- RAGAS production evaluation ---
    # Fraction of production queries that trigger async RAGAS scoring (0.0–1.0).
    # Set to 0.0 to disable entirely; 1.0 to score every query.
    ragas_sample_rate: float = float(os.environ.get("RAGAS_SAMPLE_RATE", "1.0"))


settings = Settings()
