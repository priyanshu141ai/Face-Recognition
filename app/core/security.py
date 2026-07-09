import hmac

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def verify_bearer_token(authorization: str | None = Header(default=None)) -> None:
    token = get_settings().api_bearer_token
    if not token:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    if not hmac.compare_digest(authorization.split(" ", 1)[1], token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


def require_bearer_token(authorization: str | None = Header(default=None)) -> None:
    verify_bearer_token(authorization)
