import hmac

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings


service_bearer = HTTPBearer(
    scheme_name="ServiceBearer",
    description="Private service credential used only by the ESS Gateway.",
    auto_error=False,
)


def verify_bearer_token(credentials: HTTPAuthorizationCredentials | None) -> None:
    token = get_settings().api_bearer_token
    if not token:
        return
    if not credentials or credentials.scheme != "Bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    if not hmac.compare_digest(credentials.credentials, token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


def require_bearer_token(credentials: HTTPAuthorizationCredentials | None = Security(service_bearer)) -> None:
    verify_bearer_token(credentials)
