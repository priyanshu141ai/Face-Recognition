from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)


metadata = MetaData()

clients = Table(
    "clients",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("code", String(64), nullable=False, unique=True),
    Column("name", String(160), nullable=False),
    Column("active", Boolean, nullable=False, default=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

face_registrations = Table(
    "face_registrations",
    metadata,
    Column("user_id", String(128), primary_key=True),
    Column("encrypted_embedding", LargeBinary, nullable=False),
    Column("embedding_dimension", Integer, nullable=False),
    Column("detector", String(128), nullable=False),
    Column("recognizer", String(128), nullable=False),
    Column("preprocessing", String(128), nullable=False),
    Column("registered_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=True),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
    Column("encryption_key_version", Integer, nullable=False, default=1),
    Column("consent_reference", String(255), nullable=True),
    Column("calibration_version", String(128), nullable=True),
    Column("capture_count", Integer, nullable=False, default=1),
    Column("captured_angles", String(64), nullable=False, default="legacy"),
    Column("template_version", String(64), nullable=False, default="single_capture_v1"),
)

device_registrations = Table(
    "device_registrations",
    metadata,
    Column("user_id", String(128), primary_key=True),
    Column("device_id", String(255), nullable=False, unique=True),
    Column("platform", String(16), nullable=False),
    Column("public_key", Text, nullable=True),
    Column("public_key_fingerprint", String(64), nullable=True, unique=True),
    Column("key_algorithm", String(32), nullable=True),
    Column("key_version", Integer, nullable=False, default=1),
    Column("registered_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=True),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
    Column("last_verified_at", DateTime(timezone=True), nullable=True),
)

liveness_challenges = Table(
    "liveness_challenges",
    metadata,
    Column("challenge_id", String(36), primary_key=True),
    Column("user_id", String(128), nullable=False),
    Column("device_id", String(255), ForeignKey("device_registrations.device_id", ondelete="CASCADE"), nullable=False),
    Column("nonce_hash", String(64), nullable=False),
    Column("challenge_type", String(64), nullable=False),
    Column("intended_action", String(64), nullable=False),
    Column("required_capture_count", Integer, nullable=False),
    Column("issued_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("used_at", DateTime(timezone=True), nullable=True),
    Column("attempt_count", Integer, nullable=False, default=0),
    Column("status", String(32), nullable=False, default="issued"),
)
Index("ix_liveness_challenge_scope", liveness_challenges.c.user_id, liveness_challenges.c.device_id)
Index("ix_liveness_challenge_expiry", liveness_challenges.c.expires_at)

device_challenges = Table(
    "device_challenges",
    metadata,
    Column("challenge_id", String(36), primary_key=True),
    Column("user_id", String(128), nullable=False),
    Column("device_id", String(255), nullable=False),
    Column("nonce_hash", String(64), nullable=False),
    Column("operation", String(64), nullable=False),
    Column("issued_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("used_at", DateTime(timezone=True), nullable=True),
    Column("status", String(32), nullable=False, default="issued"),
)
Index("ix_device_challenge_scope", device_challenges.c.user_id, device_challenges.c.device_id)
Index("ix_device_challenge_expiry", device_challenges.c.expires_at)

replay_records = Table(
    "replay_records",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("scope_hash", String(64), nullable=False),
    Column("fingerprint", String(64), nullable=False),
    Column("kind", String(32), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("scope_hash", "fingerprint", "kind", name="uq_replay_scope_fingerprint_kind"),
)
Index("ix_replay_expiry", replay_records.c.expires_at)

security_attempts = Table(
    "security_attempts",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("scope_hash", String(64), nullable=False),
    Column("action", String(64), nullable=False),
    Column("failed_count", Integer, nullable=False, default=0),
    Column("first_failure_at", DateTime(timezone=True), nullable=True),
    Column("last_failure_at", DateTime(timezone=True), nullable=True),
    Column("cooldown_until", DateTime(timezone=True), nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("scope_hash", "action", name="uq_security_attempt_scope_action"),
)
Index("ix_security_attempt_cooldown", security_attempts.c.cooldown_until)

security_audit_events = Table(
    "security_audit_events",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("event_type", String(64), nullable=False),
    Column("subject_hash", String(64), nullable=True),
    Column("device_hash", String(64), nullable=True),
    Column("request_id", String(128), nullable=True),
    Column("outcome", String(32), nullable=False),
    Column("reason_code", String(64), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
Index("ix_security_audit_created", security_audit_events.c.created_at)
Index("ix_security_audit_subject", security_audit_events.c.subject_hash)
