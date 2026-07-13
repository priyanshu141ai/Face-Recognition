from sqlalchemy import select

from app.persistence.schema import security_audit_events
from app.services.ess_repository import EssRepository
from app.services.security_audit import SecurityAuditService


def test_security_audit_stores_only_privacy_safe_identifiers(tmp_path) -> None:
    repository = EssRepository(str(tmp_path / "audit.sqlite3"))
    audit = SecurityAuditService(repository, "audit-hmac-key")
    audit.record(
        "device_signature_failed", "blocked", user_id="employee-raw-id",
        device_id="device-raw-id", request_id="safe-request-id", reason_code="invalid_signature",
    )
    with repository.database.engine.connect() as connection:
        row = connection.execute(select(security_audit_events)).mappings().one()
    serialized = str(dict(row))
    assert "employee-raw-id" not in serialized
    assert "device-raw-id" not in serialized
    assert len(row["subject_hash"]) == 64
    assert len(row["device_hash"]) == 64
    assert "image" not in row
    assert "embedding" not in row
    assert "signature" not in row
