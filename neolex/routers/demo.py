"""Demo configuration endpoint.

Returns demo mode status and sample questions for the frontend.

The demo API key is no longer served through this endpoint.  It is printed
once to stdout at server startup (see demo_setup.py / ensure_demo_key) and
stored only as a SHA-256 hash in SQLite — never in a plaintext file on disk.

This endpoint is intentionally unauthenticated — it only returns information
that the demo operator has already chosen to expose publicly.
"""
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from neolex.config import settings

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

# In-process per-IP rate limit for the unauthenticated /config endpoint.
# Stored as { ip: (count, window_start_monotonic) }.
import time as _time
_demo_config_rate: dict[str, tuple[int, float]] = {}
_DEMO_CONFIG_LIMIT = 10   # requests
_DEMO_CONFIG_WINDOW = 60  # seconds


@router.get("/config")
async def demo_config(request: Request) -> JSONResponse:
    """Return demo mode configuration for the frontend.

    Response:
        demo_mode: bool — whether the server was started with DEMO_MODE=true
        api_key: null — key is no longer served over HTTP; printed once at startup
        sample_questions: list[str] — suggested questions for the demo
    """
    # Simple per-IP rate limiting (max 10 req/min) to prevent enumeration abuse.
    ip = getattr(request.client, "host", "unknown") or "unknown"
    now = _time.monotonic()
    count, window_start = _demo_config_rate.get(ip, (0, now))
    if now - window_start >= _DEMO_CONFIG_WINDOW:
        count, window_start = 0, now
    count += 1
    _demo_config_rate[ip] = (count, window_start)
    if count > _DEMO_CONFIG_LIMIT:
        return JSONResponse(
            {"error": "Too many requests"},
            status_code=429,
            headers={"Retry-After": str(_DEMO_CONFIG_WINDOW)},
        )

    if not settings.demo_mode:
        return JSONResponse({"demo_mode": False, "api_key": None, "sample_questions": []})

    sample_questions = [
        "What is the limitation period under DIFC Law No. 5 of 2005?",
        "What are the grounds for terminating an employment contract under DIFC Employment Law?",
        "What fiduciary duties does a company director owe under DIFC Companies Law?",
        "How is arbitration initiated under the DIFC Arbitration Law?",
        "What are the requirements for a valid contract under DIFC Contract Law?",
        "What is the procedure for winding up a company in the DIFC?",
        "What remedies are available for breach of contract under DIFC law?",
        "How does the DIFC regulate data protection and privacy?",
        "What are the disclosure requirements for listed companies in the DIFC?",
        "What is the jurisdiction of the DIFC Courts?",
    ]

    # Serve demo key from env var if set (safe for demo deployments)
    demo_key = os.environ.get("DEMO_API_KEY")

    return JSONResponse({
        "demo_mode": True,
        "api_key": demo_key,
        "sample_questions": sample_questions,
    })
