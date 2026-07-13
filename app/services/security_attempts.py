from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.security_errors import SecurityDomainError
from app.services.ess_repository import EssRepository
from app.services.security_audit import SecurityAuditService


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class SecurityAttemptService:
    def __init__(
        self,
        repository: EssRepository,
        audit: SecurityAuditService,
        *,
        window_seconds: int,
        failure_limit: int,
        cooldown_seconds: int,
    ) -> None:
        self.repository = repository
        self.audit = audit
        self.window_seconds = window_seconds
        self.failure_limit = failure_limit
        self.cooldown_seconds = cooldown_seconds

    def _scope(self, user_id: str, device_id: str) -> str:
        return self.audit.privacy_hash(f"{user_id}:{device_id}") or ""

    def ensure_allowed(self, user_id: str, device_id: str, action: str = "face_verify") -> None:
        record = self.repository.get_security_attempt(self._scope(user_id, device_id), action)
        now = datetime.now(timezone.utc)
        if record and record["cooldown_until"] and _utc(record["cooldown_until"]) > now:
            retry = max(1, int((_utc(record["cooldown_until"]) - now).total_seconds()))
            raise SecurityDomainError(
                "cooldown_active",
                "Too many failed attempts. Try again later.",
                status_code=429,
                retry_after_seconds=retry,
            )
        if record and record["cooldown_until"] and _utc(record["cooldown_until"]) <= now:
            self.repository.clear_security_attempt(self._scope(user_id, device_id), action)
            self.audit.record(
                "face_cooldown_ended", "allowed", user_id=user_id, device_id=device_id,
                reason_code="cooldown_elapsed"
            )

    def failure(self, user_id: str, device_id: str, action: str = "face_verify") -> None:
        scope, now = self._scope(user_id, device_id), datetime.now(timezone.utc)
        record = self.repository.get_security_attempt(scope, action)
        if not record or not record["first_failure_at"] or _utc(record["first_failure_at"]) < now - timedelta(seconds=self.window_seconds):
            count, first = 1, now
        else:
            count, first = int(record["failed_count"]) + 1, _utc(record["first_failure_at"])
        cooldown = None
        if count >= self.failure_limit:
            multiplier = min(4, max(1, count // self.failure_limit))
            cooldown = now + timedelta(seconds=self.cooldown_seconds * multiplier)
            self.audit.record("face_cooldown_started", "blocked", user_id=user_id, device_id=device_id, reason_code="failure_limit")
        self.repository.save_security_attempt(
            scope,
            action,
            failed_count=count,
            first_failure_at=first,
            last_failure_at=now,
            cooldown_until=cooldown,
        )

    def success(self, user_id: str, device_id: str, action: str = "face_verify") -> None:
        self.repository.clear_security_attempt(self._scope(user_id, device_id), action)
