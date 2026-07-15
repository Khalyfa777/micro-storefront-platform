"""add store access events

Revision ID: a6c8e1f3b5d7
Revises: f4b7c9d2e1a6
Create Date: 2026-07-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a6c8e1f3b5d7"
down_revision: str | None = (
    "f4b7c9d2e1a6"
)
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "store_access_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "actor_role",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "action",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "previous_is_active",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "new_is_active",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "previous_is_suspended",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "new_is_suspended",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "previous_subscription_status",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "new_subscription_status",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "action IN ("
                "'activate', "
                "'deactivate', "
                "'suspend', "
                "'unsuspend'"
                ")"
            ),
            name=(
                "ck_store_access_events_action"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            name=(
                "fk_store_access_events_"
                "store_id_stores"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=(
                "fk_store_access_events_"
                "actor_user_id_users"
            ),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_store_access_events",
        ),
    )

    op.create_index(
        (
            "ix_store_access_events_"
            "store_created_at_id_desc"
        ),
        "store_access_events",
        [
            "store_id",
            sa.text("created_at DESC"),
            sa.text("id DESC"),
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        (
            "ix_store_access_events_"
            "store_created_at_id_desc"
        ),
        table_name="store_access_events",
    )

    op.drop_table("store_access_events")