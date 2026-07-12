"""add publication state and seed plan catalog

Revision ID: c4f1d2a9e6b7
Revises: b0686dec2bbd
Create Date: 2026-07-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4f1d2a9e6b7"
down_revision: Union[str, None] = "b0686dec2bbd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PLAN_ROWS = [
    {
        "id": "11111111-1111-4111-8111-111111111111",
        "name": "starter",
        "display_name": "Starter",
        "monthly_fee": "30.00",
        "product_limit": 10,
        "can_upload_images": True,
        "can_use_custom_domain": False,
        "can_receive_online_payments": True,
        "is_quote_only": False,
        "is_active": True,
    },
    {
        "id": "22222222-2222-4222-8222-222222222222",
        "name": "business",
        "display_name": "Business",
        "monthly_fee": "80.00",
        "product_limit": 100,
        "can_upload_images": True,
        "can_use_custom_domain": False,
        "can_receive_online_payments": True,
        "is_quote_only": False,
        "is_active": True,
    },
    {
        "id": "33333333-3333-4333-8333-333333333333",
        "name": "premium",
        "display_name": "Premium",
        "monthly_fee": "150.00",
        "product_limit": None,
        "can_upload_images": True,
        "can_use_custom_domain": True,
        "can_receive_online_payments": True,
        "is_quote_only": False,
        "is_active": True,
    },
    {
        "id": "44444444-4444-4444-8444-444444444444",
        "name": "custom",
        "display_name": "Custom",
        "monthly_fee": "0.00",
        "product_limit": None,
        "can_upload_images": True,
        "can_use_custom_domain": True,
        "can_receive_online_payments": True,
        "is_quote_only": True,
        "is_active": True,
    },
]


def upgrade() -> None:
    op.add_column(
        "subscription_plans",
        sa.Column(
            "is_quote_only",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # Existing stores must remain visible after this migration.
    op.add_column(
        "stores",
        sa.Column(
            "publication_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'published'"),
        ),
    )

    op.create_check_constraint(
        "ck_stores_publication_status",
        "stores",
        "publication_status IN ('draft', 'published')",
    )

    # Future stores should default to Draft.
    op.alter_column(
        "stores",
        "publication_status",
        existing_type=sa.String(length=20),
        existing_nullable=False,
        existing_server_default=sa.text("'published'"),
        server_default=sa.text("'draft'"),
    )

    connection = op.get_bind()

    existing_plan_names = connection.execute(
        sa.text(
            """
            SELECT name
            FROM subscription_plans
            ORDER BY name
            """
        )
    ).scalars().all()

    if existing_plan_names:
        raise RuntimeError(
            "Cannot install the approved StorePlug plan catalog because "
            "subscription_plans already contains rows: "
            + ", ".join(existing_plan_names)
            + ". Audit that environment before applying this migration."
        )

    insert_plan = sa.text(
        """
        INSERT INTO subscription_plans (
            id,
            name,
            display_name,
            monthly_fee,
            product_limit,
            can_upload_images,
            can_use_custom_domain,
            can_receive_online_payments,
            is_quote_only,
            is_active
        )
        VALUES (
            CAST(:id AS uuid),
            :name,
            :display_name,
            CAST(:monthly_fee AS numeric(10, 2)),
            :product_limit,
            :can_upload_images,
            :can_use_custom_domain,
            :can_receive_online_payments,
            :is_quote_only,
            :is_active
        )
        """
    )

    for plan in PLAN_ROWS:
        connection.execute(insert_plan, plan)


def downgrade() -> None:
    connection = op.get_bind()

    for plan in PLAN_ROWS:
        connection.execute(
            sa.text(
                """
                DELETE FROM subscription_plans
                WHERE id = CAST(:plan_id AS uuid)
                """
            ),
            {"plan_id": plan["id"]},
        )

    op.drop_constraint(
        "ck_stores_publication_status",
        "stores",
        type_="check",
    )

    op.drop_column(
        "stores",
        "publication_status",
    )

    op.drop_column(
        "subscription_plans",
        "is_quote_only",
    )
