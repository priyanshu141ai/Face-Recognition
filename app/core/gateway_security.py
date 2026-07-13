from collections.abc import Callable
import hmac
from typing import Annotated

from fastapi import Depends, Request, Security
from fastapi.security import APIKeyHeader

from app.api.dependencies import audit_service, repository_dependency
from app.core.config import get_settings
from app.core.security_errors import SecurityDomainError
from app.schemas.gateway import GatewayAssertionClaims
from app.services.ess_repository import EssRepository
from app.services.gateway_assertions import GatewayAssertionService


gateway_assertion_header = APIKeyHeader(
    name="X-Gateway-Assertion",
    scheme_name="GatewayAssertion",
    description="Short-lived ES256 assertion issued by the trusted ESS Gateway.",
    auto_error=False,
)


def gateway_action(
    action: str,
    *,
    require_active_device: bool = True,
) -> Callable[..., GatewayAssertionClaims | None]:
    def dependency(
        request: Request,
        assertion: Annotated[str | None, Security(gateway_assertion_header)] = None,
        repository: EssRepository = Depends(repository_dependency),
    ) -> GatewayAssertionClaims | None:
        settings = get_settings()
        if not assertion:
            if settings.gateway_assertion_required or not settings.allow_unsigned_identity_headers:
                audit_service(repository).record("gateway_direct_access_blocked", "blocked", reason_code="direct_mobile_access_rejected")
                raise SecurityDomainError("gateway_assertion_missing", "A signed gateway assertion is required.", status_code=401)
            return None
        cached = getattr(request.state, "gateway_claims", None)
        if cached is not None:
            return cached
        audit = audit_service(repository)
        claims = GatewayAssertionService(settings, repository, audit).verify(
            assertion,
            method=request.method,
            path=request.url.path,
            request_id=request.headers.get("X-Request-ID"),
            expected_action=action,
            require_active_device=require_active_device,
        )
        compatibility_user = request.headers.get("X-User-ID")
        compatibility_device = request.headers.get("X-Device-ID")
        if compatibility_user and not hmac.compare_digest(compatibility_user, claims.user_id):
            audit.record("gateway_assertion_rejected", "blocked", user_id=claims.user_id, device_id=claims.device_id, request_id=claims.request_id, reason_code="gateway_user_mismatch")
            raise SecurityDomainError("gateway_user_mismatch", "Identity header does not match the signed assertion.", status_code=403)
        if compatibility_device and not hmac.compare_digest(compatibility_device, claims.device_id):
            audit.record("gateway_assertion_rejected", "blocked", user_id=claims.user_id, device_id=claims.device_id, request_id=claims.request_id, reason_code="gateway_device_mismatch")
            raise SecurityDomainError("gateway_device_mismatch", "Device header does not match the signed assertion.", status_code=403)
        request.state.gateway_claims = claims
        return claims

    return dependency


def require_body_binding(
    claims: GatewayAssertionClaims | None,
    *,
    request_id: str | None = None,
    device_id: str | None = None,
    platform: str | None = None,
) -> None:
    if claims is None:
        return
    if request_id is not None and request_id != claims.request_id:
        raise SecurityDomainError("gateway_request_mismatch", "Gateway assertion does not match the request body.", status_code=403)
    if device_id is not None and device_id != claims.device_id:
        raise SecurityDomainError("gateway_device_mismatch", "Gateway assertion device does not match the request body.", status_code=403)
    if platform is not None and claims.device_attestation and platform != claims.device_attestation.platform:
        raise SecurityDomainError("device_attestation_platform_mismatch", "Device platform does not match attestation.", status_code=403)
