import pytest

from app.core.security_errors import SecurityDomainError
from app.services.ess_repository import EssRepository
from app.services.security_attempts import SecurityAttemptService
from app.services.security_audit import SecurityAuditService


def test_cooldown_and_success_reset(tmp_path) -> None:
    repository = EssRepository(str(tmp_path / "db.sqlite3"))
    service = SecurityAttemptService(
        repository, SecurityAuditService(repository, "audit"),
        window_seconds=60, failure_limit=2, cooldown_seconds=60,
    )
    service.failure("user-a", "device-a")
    service.ensure_allowed("user-a", "device-a")
    service.failure("user-a", "device-a")
    with pytest.raises(SecurityDomainError) as blocked:
        service.ensure_allowed("user-a", "device-a")
    assert blocked.value.code == "cooldown_active"
    assert blocked.value.retry_after_seconds >= 1
    service.success("user-a", "device-a")
    service.ensure_allowed("user-a", "device-a")
