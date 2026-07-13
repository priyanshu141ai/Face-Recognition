from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from app.core.config import Settings
from app.core.security_errors import SecurityDomainError
from app.persistence.schema import liveness_challenges
from app.schemas.common import ImagePayload
from app.schemas.liveness import LivenessEvidence
from app.services.ess_repository import EssRepository
from app.services.liveness.challenge_service import LivenessChallengeService
from app.services.liveness.providers import MockLivenessProvider
from app.services.replay_protection import ReplayProtectionService
from app.services.security_audit import SecurityAuditService


def _service(tmp_path):
    repository = EssRepository(str(tmp_path / "db.sqlite3"))
    repository.register_device("user-a", "phone-001", "android", None)
    repository.register_device("user-b", "phone-002", "ios", None)
    settings = Settings(
        liveness_provider="mock", liveness_required=True,
        liveness_required_capture_count=3, liveness_challenge_ttl_seconds=90,
        capture_max_age_seconds=120, audit_hash_key="audit-key",
    )
    audit = SecurityAuditService(repository, settings.audit_hash_key)
    replay = ReplayProtectionService(repository, audit, settings.replay_window_seconds)
    return repository, LivenessChallengeService(repository, MockLivenessProvider(), replay, audit, settings)


def _evidence(challenge) -> LivenessEvidence:
    return LivenessEvidence(
        challenge_id=challenge.challenge_id,
        challenge_nonce=challenge.nonce,
        capture_timestamp=datetime.now(timezone.utc),
        challenge_action=challenge.challenge_type,
        frames=[ImagePayload(kind="base64_png", data="x") for _ in range(3)],
    )


def test_valid_challenge_is_single_use(tmp_path) -> None:
    _, service = _service(tmp_path)
    challenge = service.issue("user-a", "phone-001", "face_verify")
    result = service.evaluate(
        _evidence(challenge), user_id="user-a", device_id="phone-001",
        frame_bytes=[b"one", b"two", b"three"], intended_action="face_verify",
    )
    assert result.approved is True
    with pytest.raises(SecurityDomainError) as reused:
        service.evaluate(
            _evidence(challenge), user_id="user-a", device_id="phone-001",
            frame_bytes=[b"four", b"five", b"six"], intended_action="face_verify",
        )
    assert reused.value.code == "challenge_reused"


@pytest.mark.parametrize("case,code", [
    ("user", "challenge_user_mismatch"),
    ("device", "challenge_device_mismatch"),
    ("action", "challenge_scope_invalid"),
    ("nonce", "challenge_nonce_invalid"),
    ("challenge_action", "challenge_action_mismatch"),
])
def test_challenge_scope_is_enforced(tmp_path, case, code) -> None:
    _, service = _service(tmp_path)
    challenge = service.issue("user-a", "phone-001", "face_verify")
    evidence = _evidence(challenge)
    user, device, action = "user-a", "phone-001", "face_verify"
    if case == "user":
        user = "user-b"
    elif case == "device":
        device = "phone-002"
    elif case == "action":
        action = "face_register"
    elif case == "nonce":
        evidence.challenge_nonce = "x" * 32
    else:
        evidence.challenge_action = "center_face" if challenge.challenge_type != "center_face" else "turn_head_left"
    with pytest.raises(SecurityDomainError) as error:
        service.evaluate(
            evidence, user_id=user, device_id=device,
            frame_bytes=[b"one", b"two", b"three"], intended_action=action,
        )
    assert error.value.code == code


def test_expired_missing_and_duplicate_capture_are_rejected(tmp_path) -> None:
    repository, service = _service(tmp_path)
    with pytest.raises(SecurityDomainError) as missing:
        service.evaluate(
            None, user_id="user-a", device_id="phone-001", frame_bytes=[],
            intended_action="face_verify",
        )
    assert missing.value.code == "challenge_missing"

    expired = service.issue("user-a", "phone-001", "face_verify")
    with repository.database.engine.begin() as connection:
        connection.execute(update(liveness_challenges).where(
            liveness_challenges.c.challenge_id == expired.challenge_id
        ).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    with pytest.raises(SecurityDomainError) as error:
        service.evaluate(
            _evidence(expired), user_id="user-a", device_id="phone-001",
            frame_bytes=[b"a", b"b", b"c"], intended_action="face_verify",
        )
    assert error.value.code == "challenge_expired"

    first = service.issue("user-a", "phone-001", "face_verify")
    frames = [b"same-1", b"same-2", b"same-3"]
    service.evaluate(
        _evidence(first), user_id="user-a", device_id="phone-001",
        frame_bytes=frames, intended_action="face_verify",
    )
    second = service.issue("user-a", "phone-001", "face_verify")
    with pytest.raises(SecurityDomainError) as replay:
        service.evaluate(
            _evidence(second), user_id="user-a", device_id="phone-001",
            frame_bytes=frames, intended_action="face_verify",
        )
    assert replay.value.code == "replay_detected"
