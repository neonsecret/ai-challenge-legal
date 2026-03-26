"""Demo configuration endpoint.

Returns demo mode status and, when DEMO_MODE=true, a pre-created demo API key
stored in a well-known file (.demo_key) so the frontend can auto-fill it.

This endpoint is intentionally unauthenticated — it only returns information
that the demo operator has already chosen to expose publicly.
"""
import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from neolex.config import settings

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

# The demo key is written to .demo_key by demo_setup.py / Makefile.
_DEMO_KEY_FILE = Path(".demo_key")


@router.get("/config")
async def demo_config() -> JSONResponse:
    """Return demo mode configuration for the frontend.

    Response:
        demo_mode: bool — whether the server was started with DEMO_MODE=true
        api_key: str | null — the demo API key (only present in demo mode)
        sample_questions: list[str] — suggested questions for the demo
    """
    if not settings.demo_mode:
        return JSONResponse({"demo_mode": False, "api_key": None, "sample_questions": []})

    # Read the demo key from file if it was written by demo_setup.py
    api_key: str | None = None
    if _DEMO_KEY_FILE.exists():
        raw = _DEMO_KEY_FILE.read_text().strip()
        if raw:
            api_key = raw

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

    return JSONResponse({
        "demo_mode": True,
        "api_key": api_key,
        "sample_questions": sample_questions,
    })
