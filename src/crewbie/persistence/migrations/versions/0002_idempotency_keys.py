"""idempotency keys

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("install_id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=100), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["install_id"],
            ["installs.id"],
            name=op.f("fk_idempotency_keys_install_id_installs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("install_id", "key", name=op.f("pk_idempotency_keys")),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
