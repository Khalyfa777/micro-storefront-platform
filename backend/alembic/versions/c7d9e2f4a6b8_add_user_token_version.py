"""add user token version

Revision ID: c7d9e2f4a6b8
Revises: a6c8e1f3b5d7
Create Date: 2026-07-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c7d9e2f4a6b8"
down_revision: str | None = (
    "a6c8e1f3b5d7"
)
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "users",
        "token_version",
    )
