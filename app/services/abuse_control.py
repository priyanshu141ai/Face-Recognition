from __future__ import annotations

import hashlib

from fastapi import Request

from app.core.security_errors import SecurityDomainError
from app.services.ess_repository import EssRepository
from app.services.rate_limit.base import RateLimiter
from app.services.security_audit import SecurityAuditService


class AbuseControlService:
    def __init__(
        self,
        limiter: RateLimiter,
        audit: SecurityAuditService,
        repository: EssRepository,
    ) -> None:
        self.limiter = limiter
        self.audit = audit
        self.repository = repository

    @staticmethod
    def _key(action: str, scope: str, value: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return f"{action}:{scope}:{digest}"

    def check(
        self,
        request: Request,
        action: str,
        *,
        limit: int,
        window_seconds: int,
        user_id: str | None = None,
        device_id: str | None = None,
    ) -> None:
        ip = request.client.host if request.client else "unknown"
        scopes = [("ip", ip)]
        if user_id:
            scopes.append(("user", user_id))
        if device_id:
            scopes.append(("device", device_id))
        for scope, value in scopes:
            retry = self.limiter.retry_after(self._key(action, scope, value), limit, window_seconds)
            if retry is not None:
                self.audit.record(
                    "rate_limit_triggered",
                    "blocked",
                    user_id=user_id,
                    device_id=device_id,
                    reason_code=action,
                )
                raise SecurityDomainError(
                    "rate_limited",
                    "Too many attempts. Try again later.",
                    status_code=429,
                    retry_after_seconds=retry,
                )
