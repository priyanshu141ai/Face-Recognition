from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.config import Settings
from app.core.security_errors import SecurityDomainError
from app.schemas.liveness import LivenessEvidence
from app.services.ess_repository import EssRepository
from app.services.liveness.base import LivenessProvider, LivenessResult
from app.services.replay_protection import ReplayProtectionService
from app.services.security_audit import SecurityAuditService


CHALLENGE_TYPES = ("turn_head_left", "turn_head_right", "center_face", "multi_frame_capture")


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@dataclass(frozen=True)
class IssuedLivenessChallenge:
    challenge_id: str
    nonce: str
    challenge_type: str
    intended_action: str
    issued_at: datetime
    expires_at: datetime
    required_capture_count: int


class LivenessChallengeService:
    def __init__(
        self,
        repository: EssRepository,
        provider: LivenessProvider,
        replay: ReplayProtectionService,
        audit: SecurityAuditService,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.provider = provider
        self.replay = replay
        self.audit = audit
        self.settings = settings

    def issue(self, user_id: str, device_id: str, intended_action: str) -> IssuedLivenessChallenge:
        now = datetime.now(timezone.utc)
        nonce = secrets.token_urlsafe(32)
        result = IssuedLivenessChallenge(
            challenge_id=str(uuid4()),
            nonce=nonce,
            challenge_type=secrets.choice(CHALLENGE_TYPES),
            intended_action=intended_action,
            issued_at=now,
            expires_at=now + timedelta(seconds=self.settings.liveness_challenge_ttl_seconds),
            required_capture_count=self.settings.liveness_required_capture_count,
        )
        self.repository.create_liveness_challenge(
            challenge_id=result.challenge_id,
            user_id=user_id,
            device_id=device_id,
            nonce_hash=hashlib.sha256(nonce.encode("ascii")).hexdigest(),
            challenge_type=result.challenge_type,
            intended_action=result.intended_action,
            required_capture_count=result.required_capture_count,
            issued_at=result.issued_at,
            expires_at=result.expires_at,
            attempt_count=0,
            status="issued",
        )
        return result

    def evaluate(
        self,
        evidence: LivenessEvidence | None,
        *,
        user_id: str,
        device_id: str,
        frame_bytes: list[bytes],
        intended_action: str,
    ) -> LivenessResult:
        if evidence is None:
            raise SecurityDomainError("challenge_missing", "A liveness challenge is required.", status_code=422)
        record = self.repository.get_liveness_challenge(evidence.challenge_id)
        if not record:
            raise SecurityDomainError("challenge_invalid", "The liveness challenge is invalid.", status_code=422)
        now = datetime.now(timezone.utc)
        if record["used_at"] is not None:
            self.audit.record(
                "liveness_challenge", "blocked", user_id=user_id, device_id=device_id,
                reason_code="challenge_reused"
            )
            raise SecurityDomainError("challenge_reused", "The liveness challenge was already used.", status_code=409)
        if _utc(record["expires_at"]) <= now:
            self.audit.record("liveness_challenge", "blocked", user_id=user_id, device_id=device_id, reason_code="challenge_expired")
            raise SecurityDomainError("challenge_expired", "The liveness challenge has expired.", status_code=409)
        if record["user_id"] != user_id:
            raise SecurityDomainError("challenge_user_mismatch", "The challenge does not belong to this user.", status_code=403)
        if record["device_id"] != device_id:
            raise SecurityDomainError("challenge_device_mismatch", "The challenge does not belong to this device.", status_code=403)
        if record["intended_action"] != intended_action:
            raise SecurityDomainError("challenge_scope_invalid", "The challenge is not valid for this action.", status_code=403)
        if record["challenge_type"] != evidence.challenge_action:
            raise SecurityDomainError("challenge_action_mismatch", "The requested challenge action was not completed.", status_code=422)
        if not secrets.compare_digest(
            str(record["nonce_hash"]), hashlib.sha256(evidence.challenge_nonce.encode("utf-8")).hexdigest()
        ):
            raise SecurityDomainError("challenge_nonce_invalid", "The liveness challenge nonce is invalid.", status_code=403)
        capture = _utc(evidence.capture_timestamp)
        if capture < _utc(record["issued_at"]) or capture > _utc(record["expires_at"]):
            raise SecurityDomainError("capture_timestamp_invalid", "The capture timestamp is outside the challenge window.", status_code=422)
        if capture < now - timedelta(seconds=self.settings.capture_max_age_seconds) or capture > now + timedelta(seconds=30):
            raise SecurityDomainError("capture_timestamp_invalid", "The capture timestamp is not current.", status_code=422)
        if len(frame_bytes) < int(record["required_capture_count"]):
            raise SecurityDomainError("capture_count_insufficient", "More camera frames are required.", status_code=422)

        attempts = self.repository.increment_liveness_attempt(evidence.challenge_id)
        if attempts > self.settings.liveness_max_attempts:
            raise SecurityDomainError("challenge_attempts_exceeded", "The liveness challenge has too many attempts.", status_code=429)
        self.replay.claim_frames(user_id, device_id, frame_bytes)
        result = self.provider.evaluate(
            frame_bytes,
            record,
            evidence.provider_assertion,
            capture.isoformat(),
        )
        if not result.approved:
            self.audit.record("liveness_failed", "rejected", user_id=user_id, device_id=device_id, reason_code=result.reason_code)
            raise SecurityDomainError("liveness_failed", "Liveness verification failed.", status_code=403)
        if not self.repository.consume_liveness_challenge(evidence.challenge_id):
            raise SecurityDomainError("challenge_reused", "The liveness challenge was already used.", status_code=409)
        self.audit.record("liveness_passed", "allowed", user_id=user_id, device_id=device_id, reason_code=result.reason_code)
        return result
