from app.core.config import get_settings
from app.persistence.database import database_url_from_settings
from app.services.abuse_control import AbuseControlService
from app.services.device_proof import DeviceProofService
from app.services.ess_repository import EssRepository, cached_repository
from app.services.liveness.challenge_service import LivenessChallengeService
from app.services.liveness.providers import build_liveness_provider
from app.services.rate_limit.factory import build_rate_limiter
from app.services.replay_protection import ReplayProtectionService
from app.services.security_attempts import SecurityAttemptService
from app.services.security_audit import SecurityAuditService


def repository_dependency() -> EssRepository:
    settings = get_settings()
    return cached_repository(
        database_url_from_settings(settings),
        settings.database_auto_create,
        settings.db_pool_size,
        settings.db_max_overflow,
        settings.db_connect_timeout_seconds,
    )


def audit_service(repository: EssRepository) -> SecurityAuditService:
    return SecurityAuditService(repository, get_settings().audit_hash_key)


def abuse_service(repository: EssRepository) -> AbuseControlService:
    return AbuseControlService(build_rate_limiter(get_settings()), audit_service(repository), repository)


def device_proof_service(repository: EssRepository) -> DeviceProofService:
    return DeviceProofService(repository, get_settings().device_challenge_ttl_seconds)


def liveness_service(repository: EssRepository) -> LivenessChallengeService:
    settings = get_settings()
    audit = audit_service(repository)
    replay = ReplayProtectionService(repository, audit, settings.replay_window_seconds)
    return LivenessChallengeService(
        repository,
        build_liveness_provider(settings),
        replay,
        audit,
        settings,
    )


def attempt_service(repository: EssRepository) -> SecurityAttemptService:
    settings = get_settings()
    return SecurityAttemptService(
        repository,
        audit_service(repository),
        window_seconds=settings.failed_face_attempt_window_seconds,
        failure_limit=settings.failed_face_attempt_limit,
        cooldown_seconds=settings.face_cooldown_seconds,
    )
