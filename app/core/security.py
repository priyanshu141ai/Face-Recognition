import os
from fastapi import Header, HTTPException, status


def require_bearer_token(authorization: str | None = Header(default=None)) -> None:
    token = os.getenv("API_BEARER_TOKEN")
    if not token:
        return
    if not authorization or not authorization.startswith("Bearer ") or authorization.split(" ", 1)[1] != token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
