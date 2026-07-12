"""add seller invitations

Revision ID: b0686dec2bbd
Revises: 8e75ad7a3a5e
Create Date: 2026-07-12 15:27:31.613054

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b0686dec2bbd"
down_revision: Union[str, None] = "8e75ad7a3a5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(length=255),
        existing_nullable=False,
        nullable=True,
    )

    op.add_column(
        "users",
        sa.Column(
            "phone_number",
            sa.String(length=30),
            nullable=True,
        ),
    )

    op.create_table(
        "seller_invitations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "token_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_seller_invitations_created_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            name="fk_seller_invitations_store_id_stores",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_seller_invitations_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_seller_invitations",
        ),
        sa.UniqueConstraint(
            "token_hash",
            name="uq_seller_invitations_token_hash",
        ),
    )

    op.create_index(
        "ix_seller_invitations_user_id",
        "seller_invitations",
        ["user_id"],
        unique=False,
    )

    op.create_index(
        "ix_seller_invitations_store_id",
        "seller_invitations",
        ["store_id"],
        unique=False,
    )

    op.create_index(
        "ix_seller_invitations_expires_at",
        "seller_invitations",
        ["expires_at"],
        unique=False,
    )

    op.create_index(
        "uq_seller_invitations_one_open_per_user",
        "seller_invitations",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text(
            "accepted_at IS NULL AND revoked_at IS NULL"
        ),
    )


def downgrade() -> None:
    connection = op.get_bind()

    null_password_count = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM users
            WHERE password_hash IS NULL
            """
        )
    ).scalar_one()

    if null_password_count:
        raise RuntimeError(
            "Cannot downgrade while invited users still have NULL password hashes. "
            "Activate or remove those accounts before retrying."
        )

    op.drop_index(
        "uq_seller_invitations_one_open_per_user",
        table_name="seller_invitations",
    )
    op.drop_index(
        "ix_seller_invitations_expires_at",
        table_name="seller_invitations",
    )
    op.drop_index(
        "ix_seller_invitations_store_id",
        table_name="seller_invitations",
    )
    op.drop_index(
        "ix_seller_invitations_user_id",
        table_name="seller_invitations",
    )

    op.drop_table("seller_invitations")

    op.drop_column(
        "users",
        "phone_number",
    )

    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(length=255),
        existing_nullable=True,
        nullable=False,
    )
