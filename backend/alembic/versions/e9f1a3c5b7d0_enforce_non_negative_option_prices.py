"""enforce non-negative finite option prices

Revision ID: e9f1a3c5b7d0
Revises: d8e1f3a5c7b9
Create Date: 2026-07-17
"""

from collections.abc import Sequence

from alembic import op


revision: str = "e9f1a3c5b7d0"
down_revision: str | None = "d8e1f3a5c7b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT_NAME = (
    "ck_product_order_option_price_non_negative_finite"
)
CONSTRAINT_SQL = (
    "price_adjustment >= 0 "
    "AND price_adjustment < 'Infinity'::numeric"
)


def upgrade() -> None:
    op.create_check_constraint(
        CONSTRAINT_NAME,
        "product_order_field_options",
        CONSTRAINT_SQL,
    )


def downgrade() -> None:
    op.drop_constraint(
        CONSTRAINT_NAME,
        "product_order_field_options",
        type_="check",
    )
