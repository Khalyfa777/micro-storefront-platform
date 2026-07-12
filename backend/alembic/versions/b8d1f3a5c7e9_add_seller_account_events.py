"""add seller account events

Revision ID: b8d1f3a5c7e9
Revises: a7c9e2f4b6d8
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "b8d1f3a5c7e9"
down_revision: Union[str, None] = "a7c9e2f4b6d8"
branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None
depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    op.create_table(
        "seller_account_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "seller_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "action",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "previous_account_status",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "new_account_status",
            sa.String(length=20),
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
            "action IN ('suspend', 'reactivate')",
            name=(
                "ck_seller_account_events_action"
            ),
        ),
        sa.CheckConstraint(
            (
                "previous_account_status "
                "IN ('active', 'suspended')"
            ),
            name=(
                "ck_seller_account_events_"
                "previous_status"
            ),
        ),
        sa.CheckConstraint(
            (
                "new_account_status "
                "IN ('active', 'suspended')"
            ),
            name=(
                "ck_seller_account_events_"
                "new_status"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["seller_id"],
            ["users.id"],
            name=(
                "fk_seller_account_events_"
                "seller_id_users"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=(
                "fk_seller_account_events_"
                "actor_user_id_users"
            ),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_seller_account_events",
        ),
    )

    op.create_index(
        (
            "ix_seller_account_events_"
            "seller_created_at_id_desc"
        ),
        "seller_account_events",
        [
            "seller_id",
            sa.text("created_at DESC"),
            sa.text("id DESC"),
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        (
            "ix_seller_account_events_"
            "seller_created_at_id_desc"
        ),
        table_name="seller_account_events",
    )

    op.drop_table("seller_account_events")
