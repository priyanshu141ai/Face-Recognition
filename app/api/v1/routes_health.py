from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.schemas.model import ReadyResponse
from app.services.calibration import resolve_match_policy
from app.services.pipeline import get_face_verification_pipeline

router = APIRouter(prefix="", tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", response_model=ReadyResponse)
def readyz() -> dict[str, object]:
    settings = get_settings()
    try:
        resolve_match_policy(settings)
        get_face_verification_pipeline().ensure_ready()
    except Exception:
        return JSONResponse(status_code=503, content={
            "status": "not_ready", "models_loaded": False,
            "provider": settings.recognizer_provider, "version": settings.version,
            "reason": "model_or_calibration_initialization_failed",
        })
    return {
        "status": "ready",
        "models_loaded": True,
        "provider": settings.recognizer_provider,
        "version": settings.version,
    }
