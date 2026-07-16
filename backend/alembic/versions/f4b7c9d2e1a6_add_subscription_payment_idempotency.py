"""add subscription payment idempotency

Revision ID: f4b7c9d2e1a6
Revises: e3a5c7d9f1b2
Create Date: 2026-07-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f4b7c9d2e1a6"
down_revision: str | None = (
    "e3a5c7d9f1b2"
)
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "subscription_payments",
        sa.Column(
            "idempotency_key",
            sa.String(length=128),
            nullable=True,
        ),
    )

    op.add_column(
        "subscription_payments",
        sa.Column(
            "request_fingerprint",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        (
            "ck_subscription_payments_"
            "idempotency_fields_valid"
        ),
        "subscription_payments",
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
            "uq_subscription_payments_"
            "store_id_idempotency_key"
        ),
        "subscription_payments",
        [
            "store_id",
            "idempotency_key",
        ],
        unique=True,
        postgresql_where=sa.text(
            "idempotency_key IS NOT NULL"
        ),
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM subscription_payments
                WHERE payment_method IN (
                    'momo',
                    'bank',
                    'paystack'
                )
                  AND payment_reference IS NOT NULL
                  AND btrim(payment_reference) <> ''
                GROUP BY
                    payment_method,
                    lower(btrim(payment_reference))
                HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot enforce unique external payment references because duplicates exist.';
            END IF;
        END
        $$;
        """
    )

    op.create_index(
        (
            "uq_subscription_payments_"
            "external_reference"
        ),
        "subscription_payments",
        [
            "payment_method",
            sa.text(
                "lower(btrim(payment_reference))"
            ),
        ],
        unique=True,
        postgresql_where=sa.text(
            """
            payment_method IN (
                'momo',
                'bank',
                'paystack'
            )
            AND payment_reference IS NOT NULL
            AND btrim(payment_reference) <> ''
            """
        ),
    )


def downgrade() -> None:
    op.drop_index(
        (
            "uq_subscription_payments_"
            "external_reference"
        ),
        table_name="subscription_payments",
    )

    op.drop_index(
        (
            "uq_subscription_payments_"
            "store_id_idempotency_key"
        ),
        table_name="subscription_payments",
    )

    op.drop_constraint(
        (
            "ck_subscription_payments_"
            "idempotency_fields_valid"
        ),
        "subscription_payments",
        type_="check",
    )

    op.drop_column(
        "subscription_payments",
        "request_fingerprint",
    )

    op.drop_column(
        "subscription_payments",
        "idempotency_key",
    )
