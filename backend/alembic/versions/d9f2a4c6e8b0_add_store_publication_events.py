"""add store publication events

Revision ID: d9f2a4c6e8b0
Revises: b8d1f3a5c7e9
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "d9f2a4c6e8b0"
down_revision: Union[str, None] = "b8d1f3a5c7e9"
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
        "store_publication_events",
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
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "previous_publication_status",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "new_publication_status",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "readiness_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('publish', 'unpublish')",
            name=(
                "ck_store_publication_events_action"
            ),
        ),
        sa.CheckConstraint(
            (
                "previous_publication_status "
                "IN ('draft', 'published')"
            ),
            name=(
                "ck_store_publication_events_"
                "previous_status"
            ),
        ),
        sa.CheckConstraint(
            (
                "new_publication_status "
                "IN ('draft', 'published')"
            ),
            name=(
                "ck_store_publication_events_"
                "new_status"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            name=(
                "fk_store_publication_events_"
                "store_id_stores"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=(
                "fk_store_publication_events_"
                "actor_user_id_users"
            ),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_store_publication_events",
        ),
    )

    op.create_index(
        (
            "ix_store_publication_events_"
            "store_created_at_id_desc"
        ),
        "store_publication_events",
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
            "ix_store_publication_events_"
            "store_created_at_id_desc"
        ),
        table_name="store_publication_events",
    )

    op.drop_table(
        "store_publication_events"
    )
