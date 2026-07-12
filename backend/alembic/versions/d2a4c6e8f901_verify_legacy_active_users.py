"""verify legacy active user accounts

Revision ID: d2a4c6e8f901
Revises: c4f1d2a9e6b7
Create Date: 2026-07-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2a4c6e8f901"
down_revision: Union[str, None] = "c4f1d2a9e6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            UPDATE users
            SET
                is_verified = TRUE,
                updated_at = NOW()
            WHERE is_active = TRUE
              AND password_hash IS NOT NULL
              AND is_verified = FALSE
            """
        )
    )


def downgrade() -> None:
    # Deliberately irreversible.
    #
    # Reverting these users to unverified would lock legitimate legacy
    # accounts out of StorePlug. Account verification state must not be
    # destroyed during a code rollback.
    pass
