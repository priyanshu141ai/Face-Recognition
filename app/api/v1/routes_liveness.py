from fastapi import APIRouter, Depends, Request

from app.api.dependencies import liveness_service, repository_dependency
from app.api.v1.routes_ess import (
    BoundDeviceContext,
    _check_rate,
    _require_bound_device,
    _verify_existing_device_proof,
)
from app.core.config import get_settings
from app.core.gateway_security import gateway_action
from app.core.security import require_bearer_token
from app.core.security_errors import SecurityDomainError
from app.schemas.liveness import LivenessChallengeRequest, LivenessChallengeResponse
from app.schemas.gateway import GatewayAssertionClaims
from app.services.ess_repository import EssRepository
from app.services.liveness.providers import build_liveness_provider


router = APIRouter(tags=["liveness"])


@router.post("/api/ess/liveness/challenge", response_model=LivenessChallengeResponse)
def issue_liveness_challenge(
    http_request: Request,
    request: LivenessChallengeRequest | None = None,
    _: None = Depends(require_bearer_token),
    gateway: GatewayAssertionClaims | None = Depends(gateway_action("liveness_challenge")),
    context: BoundDeviceContext = Depends(_require_bound_device),
    repository: EssRepository = Depends(repository_dependency),
) -> dict[str, object]:
    settings = get_settings()
    provider = build_liveness_provider(settings)
    if provider.name == "disabled":
        raise SecurityDomainError(
            "liveness_unavailable",
            "Liveness verification is not configured.",
            status_code=503,
        )
    proof = request.device_proof if request else None
    _verify_existing_device_proof(
        repository,
        context.user_id,
        context.device_id,
        "liveness_challenge",
        proof,
    )
    _check_rate(
        http_request,
        repository,
        "liveness_challenge",
        settings.liveness_challenge_limit_per_minute,
        60,
        user_id=context.user_id,
        device_id=context.device_id,
    )
    challenge = liveness_service(repository).issue(
        context.user_id, context.device_id, request.intended_action
    )
    return challenge.__dict__
