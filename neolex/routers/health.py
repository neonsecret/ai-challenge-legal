"""GET /health endpoint — returns pipeline readiness status."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    ready = getattr(request.app.state, "ready", False)
    workers = getattr(request.app.state, "workers", 0)
    if not ready:
        return JSONResponse(
            status_code=503,
            content={"status": "starting", "pipeline_ready": False},
        )
    return {
        "status": "ready",
        "pipeline_ready": True,
        "workers": workers,
        "version": "0.1.0",
    }
