from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from app.core.security_errors import SecurityDomainError
from app.services.ess_repository import EssRepository
from app.services.security_audit import SecurityAuditService


class ReplayProtectionService:
    def __init__(
        self,
        repository: EssRepository,
        audit: SecurityAuditService,
        window_seconds: int,
    ) -> None:
        self.repository = repository
        self.audit = audit
        self.window_seconds = window_seconds

    def claim_frames(self, user_id: str, device_id: str, frames: list[bytes]) -> None:
        scope_hash = self.audit.privacy_hash(f"{user_id}:{device_id}") or ""
        frame_fingerprints = [hashlib.sha256(frame).hexdigest() for frame in frames]
        combined = hashlib.sha256("|".join(frame_fingerprints).encode("ascii")).hexdigest()
        expires = datetime.now(timezone.utc) + timedelta(seconds=self.window_seconds)
        claims = [(fingerprint, "frame") for fingerprint in frame_fingerprints]
        claims.append((combined, "image_set"))
        if not self.repository.claim_replay_records(scope_hash, claims, expires):
            self.audit.record(
                "replay_attempt", "blocked", user_id=user_id, device_id=device_id, reason_code="replay_detected"
            )
            raise SecurityDomainError(
                "replay_detected",
                "This capture was already used recently.",
                status_code=409,
            )
