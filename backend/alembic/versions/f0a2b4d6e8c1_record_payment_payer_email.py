# Record the exact payer email used for Paystack initialization.

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f0a2b4d6e8c1"
down_revision: str | None = "e9f1a3c5b7d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "payer_email",
            sa.String(length=255),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "transactions",
        "payer_email",
    )
