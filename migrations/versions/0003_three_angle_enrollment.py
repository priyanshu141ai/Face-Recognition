"""Add safe three-angle enrollment template metadata."""

from alembic import op
import sqlalchemy as sa


revision = "0003_three_angle_enrollment"
down_revision = "0002_production_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("face_registrations") as batch:
        batch.add_column(sa.Column("capture_count", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("captured_angles", sa.String(64), nullable=False, server_default="legacy"))
        batch.add_column(
            sa.Column("template_version", sa.String(64), nullable=False, server_default="single_capture_v1")
        )


def downgrade() -> None:
    with op.batch_alter_table("face_registrations") as batch:
        batch.drop_column("template_version")
        batch.drop_column("captured_angles")
        batch.drop_column("capture_count")
