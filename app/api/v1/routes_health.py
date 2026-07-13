from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.schemas.model import ReadyResponse
from app.services.calibration import resolve_match_policy
from app.services.pipeline import get_face_verification_pipeline
from app.api.dependencies import repository_dependency
from app.services.liveness.providers import build_liveness_provider
from app.services.rate_limit.redis import RedisRateLimiter
from app.services.rate_limit.factory import build_rate_limiter
from app.services.gateway_assertions import ensure_gateway_trust_ready

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
        repository_dependency().ready()
        ensure_gateway_trust_ready(settings)
        provider = build_liveness_provider(settings)
        if settings.liveness_required and not provider.production_capable:
            raise RuntimeError("production-capable liveness provider is unavailable")
        limiter = build_rate_limiter(settings)
        if isinstance(limiter, RedisRateLimiter):
            limiter.ping()
    except Exception:
        return JSONResponse(status_code=503, content={
            "status": "not_ready", "models_loaded": False,
            "provider": settings.recognizer_provider, "version": settings.version,
            "reason": "dependency_initialization_failed",
        })
    return {
        "status": "ready",
        "models_loaded": True,
        "provider": settings.recognizer_provider,
        "version": settings.version,
    }
