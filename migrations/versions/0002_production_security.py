"""Production security, lifecycle, challenge, replay, and audit schema."""

from alembic import op
import sqlalchemy as sa

revision = "0002_production_security"
down_revision = "0001_legacy_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("face_registrations") as batch:
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("encryption_key_version", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("consent_reference", sa.String(255), nullable=True))
        batch.add_column(sa.Column("calibration_version", sa.String(128), nullable=True))
    with op.batch_alter_table("device_registrations") as batch:
        batch.add_column(sa.Column("public_key_fingerprint", sa.String(64), nullable=True))
        batch.add_column(sa.Column("key_algorithm", sa.String(32), nullable=True))
        batch.add_column(sa.Column("key_version", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_unique_constraint("uq_device_public_key_fingerprint", ["public_key_fingerprint"])

    op.create_table(
        "liveness_challenges",
        sa.Column("challenge_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column(
            "device_id", sa.String(255),
            sa.ForeignKey("device_registrations.device_id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("nonce_hash", sa.String(64), nullable=False),
        sa.Column("challenge_type", sa.String(64), nullable=False),
        sa.Column("intended_action", sa.String(64), nullable=False),
        sa.Column("required_capture_count", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="issued"),
    )
    op.create_index("ix_liveness_challenge_scope", "liveness_challenges", ["user_id", "device_id"])
    op.create_index("ix_liveness_challenge_expiry", "liveness_challenges", ["expires_at"])
    op.create_table(
        "device_challenges",
        sa.Column("challenge_id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("device_id", sa.String(255), nullable=False),
        sa.Column("nonce_hash", sa.String(64), nullable=False),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="issued"),
    )
    op.create_index("ix_device_challenge_scope", "device_challenges", ["user_id", "device_id"])
    op.create_index("ix_device_challenge_expiry", "device_challenges", ["expires_at"])
    op.create_table(
        "replay_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scope_hash", sa.String(64), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scope_hash", "fingerprint", "kind", name="uq_replay_scope_fingerprint_kind"),
    )
    op.create_index("ix_replay_expiry", "replay_records", ["expires_at"])
    op.create_table(
        "security_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scope_hash", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scope_hash", "action", name="uq_security_attempt_scope_action"),
    )
    op.create_index("ix_security_attempt_cooldown", "security_attempts", ["cooldown_until"])
    op.create_table(
        "security_audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("subject_hash", sa.String(64), nullable=True),
        sa.Column("device_hash", sa.String(64), nullable=True),
        sa.Column("request_id", sa.String(128), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_security_audit_created", "security_audit_events", ["created_at"])
    op.create_index("ix_security_audit_subject", "security_audit_events", ["subject_hash"])


def downgrade() -> None:
    op.drop_table("security_audit_events")
    op.drop_table("security_attempts")
    op.drop_table("replay_records")
    op.drop_table("device_challenges")
    op.drop_table("liveness_challenges")
    with op.batch_alter_table("device_registrations") as batch:
        batch.drop_constraint("uq_device_public_key_fingerprint", type_="unique")
        for name in ("revoked_at", "updated_at", "key_version", "key_algorithm", "public_key_fingerprint"):
            batch.drop_column(name)
    with op.batch_alter_table("face_registrations") as batch:
        for name in (
            "calibration_version",
            "consent_reference",
            "encryption_key_version",
            "deleted_at",
            "revoked_at",
            "updated_at",
        ):
            batch.drop_column(name)
