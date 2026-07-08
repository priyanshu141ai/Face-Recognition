from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.security import require_bearer_token
from app.schemas.model import ReadyResponse

router = APIRouter(prefix="", tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz", response_model=ReadyResponse)
def readyz() -> dict[str, object]:
    settings = get_settings()
    return {
        "status": "ready",
        "models_loaded": True,
        "provider": settings.provider,
        "version": settings.version,
    }
