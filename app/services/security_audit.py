from __future__ import annotations

import hashlib
import hmac

from app.services.ess_repository import EssRepository


class SecurityAuditService:
    def __init__(self, repository: EssRepository, hash_key: str | None) -> None:
        self.repository = repository
        self._key = hash_key.encode("utf-8") if hash_key else None

    def privacy_hash(self, value: str | None) -> str | None:
        if value is None:
            return None
        data = value.encode("utf-8")
        return hmac.new(self._key, data, hashlib.sha256).hexdigest() if self._key else hashlib.sha256(data).hexdigest()

    def record(
        self,
        event_type: str,
        outcome: str,
        *,
        user_id: str | None = None,
        device_id: str | None = None,
        request_id: str | None = None,
        reason_code: str | None = None,
    ) -> None:
        self.repository.append_audit_event(
            event_type,
            outcome,
            subject_hash=self.privacy_hash(user_id),
            device_hash=self.privacy_hash(device_id),
            request_id=request_id,
            reason_code=reason_code,
        )
