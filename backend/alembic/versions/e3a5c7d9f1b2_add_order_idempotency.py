"""add order idempotency

Revision ID: e3a5c7d9f1b2
Revises: d9f2a4c6e8b0
Create Date: 2026-07-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e3a5c7d9f1b2"
down_revision: str | None = (
    "d9f2a4c6e8b0"
)
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "idempotency_key",
            sa.String(length=128),
            nullable=True,
        ),
    )

    op.add_column(
        "orders",
        sa.Column(
            "request_fingerprint",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        (
            "ck_orders_"
            "idempotency_fields_valid"
        ),
        "orders",
        """
        (
            idempotency_key IS NULL
            AND request_fingerprint IS NULL
        )
        OR
        (
            idempotency_key IS NOT NULL
            AND char_length(
                idempotency_key
            ) BETWEEN 16 AND 128
            AND request_fingerprint IS NOT NULL
            AND char_length(
                request_fingerprint
            ) = 64
        )
        """,
    )

    op.create_index(
        (
            "uq_orders_store_id_"
            "idempotency_key"
        ),
        "orders",
        [
            "store_id",
            "idempotency_key",
        ],
        unique=True,
        postgresql_where=sa.text(
            "idempotency_key IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        (
            "uq_orders_store_id_"
            "idempotency_key"
        ),
        table_name="orders",
    )

    op.drop_constraint(
        (
            "ck_orders_"
            "idempotency_fields_valid"
        ),
        "orders",
        type_="check",
    )

    op.drop_column(
        "orders",
        "request_fingerprint",
    )

    op.drop_column(
        "orders",
        "idempotency_key",
    )
