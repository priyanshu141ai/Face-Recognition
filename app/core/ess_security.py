import hmac
import re
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:@-]{1,128}$")
DEVICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,255}$")


def require_user_id(x_user_id: Annotated[str | None, Header(alias="X-User-ID")] = None) -> str:
    """Accept identity asserted by the trusted ESS gateway after authentication."""
    if not x_user_id or not USER_ID_PATTERN.fullmatch(x_user_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "user_identity_required", "message": "A valid X-User-ID header is required"},
        )
    return x_user_id


def require_device_id(x_device_id: Annotated[str | None, Header(alias="X-Device-ID")] = None) -> str:
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
