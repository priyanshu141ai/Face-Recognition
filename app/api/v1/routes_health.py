from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.schemas.model import ReadyResponse
from app.core.errors import CalibrationProfileError
from app.services.calibration import resolve_match_policy

router = APIRouter(prefix="", tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", response_model=ReadyResponse)
def readyz() -> dict[str, object]:
    settings = get_settings()
    try:
        resolve_match_policy(settings)
    except CalibrationProfileError as exc:
        return JSONResponse(status_code=503, content={
            "status": "not_ready", "models_loaded": False,
            "provider": settings.provider, "version": settings.version,
            "reason": exc.message,
        })
    return {
        "status": "ready",
        "models_loaded": True,
        "provider": settings.provider,
        "version": settings.version,
    }
