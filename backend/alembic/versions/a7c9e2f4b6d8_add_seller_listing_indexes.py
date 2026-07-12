"""add seller listing indexes

Revision ID: a7c9e2f4b6d8
Revises: d2a4c6e8f901
Create Date: 2026-07-12
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a7c9e2f4b6d8"
down_revision: Union[str, None] = "d2a4c6e8f901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX
            ix_users_merchants_created_at_id_desc
        ON users (
            created_at DESC,
            id DESC
        )
        WHERE role = 'merchant'
        """
    )

    op.execute(
        """
        CREATE INDEX
            ix_stores_owner_created_at_id_desc
        ON stores (
            owner_id,
            created_at DESC,
            id DESC
        )
        """
    )

    op.execute(
        """
        CREATE INDEX
            ix_seller_invitations_user_created_at_id_desc
        ON seller_invitations (
            user_id,
            created_at DESC,
            id DESC
        )
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_seller_invitations_user_created_at_id_desc",
        table_name="seller_invitations",
    )

    op.drop_index(
        "ix_stores_owner_created_at_id_desc",
        table_name="stores",
    )

    op.drop_index(
        "ix_users_merchants_created_at_id_desc",
        table_name="users",
    )
