import hmac
import re
from typing import Annotated

from fastapi import Header, HTTPException, Request, status

from app.core.config import get_settings


USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:@-]{1,128}$")
DEVICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,255}$")


def require_user_id(
    request: Request,
    x_user_id: Annotated[str | None, Header(alias="X-User-ID")] = None,
) -> str:
    claims = getattr(request.state, "gateway_claims", None)
    if claims is not None:
        if x_user_id and not hmac.compare_digest(x_user_id, claims.user_id):
            raise HTTPException(status_code=403, detail={"code": "gateway_user_mismatch", "message": "Identity header does not match the signed assertion"})
        return claims.user_id
    if get_settings().gateway_assertion_required or not get_settings().allow_unsigned_identity_headers:
        raise HTTPException(status_code=401, detail={"code": "gateway_assertion_required", "message": "A signed gateway assertion is required"})
    if not x_user_id or not USER_ID_PATTERN.fullmatch(x_user_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "user_identity_required", "message": "A valid X-User-ID header is required"},
        )
    return x_user_id


def require_device_id(
    request: Request,
    x_device_id: Annotated[str | None, Header(alias="X-Device-ID")] = None,
) -> str:
    claims = getattr(request.state, "gateway_claims", None)
    if claims is not None:
        if x_device_id and not hmac.compare_digest(x_device_id, claims.device_id):
            raise HTTPException(status_code=403, detail={"code": "gateway_device_mismatch", "message": "Device header does not match the signed assertion"})
        return claims.device_id
    if get_settings().gateway_assertion_required or not get_settings().allow_unsigned_identity_headers:
        raise HTTPException(status_code=401, detail={"code": "gateway_assertion_required", "message": "A signed gateway assertion is required"})
    if not x_device_id or not DEVICE_ID_PATTERN.fullmatch(x_device_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "device_identity_required", "message": "A valid X-Device-ID header is required"},
        )
    return x_device_id


def require_device_reset_token(
    x_device_reset_token: Annotated[str | None, Header(alias="X-Device-Reset-Token")] = None,
) -> None:
    configured = get_settings().device_reset_token
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "device_reset_not_configured", "message": "Device reset is not configured"},
        )
    if not x_device_reset_token or not hmac.compare_digest(x_device_reset_token, configured):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "device_reset_forbidden", "message": "Device reset authorization failed"},
        )
