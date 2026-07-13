"""Legacy ESS schema baseline."""

from alembic import op
import sqlalchemy as sa

revision = "0001_legacy_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "face_registrations",
        sa.Column("user_id", sa.String(128), primary_key=True),
        sa.Column("encrypted_embedding", sa.LargeBinary(), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("detector", sa.String(128), nullable=False),
        sa.Column("recognizer", sa.String(128), nullable=False),
        sa.Column("preprocessing", sa.String(128), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "device_registrations",
        sa.Column("user_id", sa.String(128), primary_key=True),
        sa.Column("device_id", sa.String(255), nullable=False, unique=True),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("device_registrations")
    op.drop_table("face_registrations")
    op.drop_table("clients")
