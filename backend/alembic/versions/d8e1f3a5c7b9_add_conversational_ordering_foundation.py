
"""add conversational ordering foundation

Revision ID: d8e1f3a5c7b9
Revises: c7d9e2f4a6b8
Create Date: 2026-07-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d8e1f3a5c7b9"
down_revision: str | None = "c7d9e2f4a6b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "default_fulfillment_method",
            sa.String(length=40),
            nullable=False,
            server_default="seller_confirmation",
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "allowed_fulfillment_methods",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("""'["seller_confirmation"]'::jsonb"""),
        ),
    )

    op.create_table(
        "product_order_fields",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("field_type", sa.String(length=30), nullable=False),
        sa.Column("placeholder", sa.String(length=255), nullable=True),
        sa.Column("help_text", sa.Text(), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("include_in_whatsapp", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "validation_rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "key ~ '^[a-z][a-z0-9_]{0,49}$'",
            name="ck_product_order_fields_key_format",
        ),
        sa.CheckConstraint(
            "NOT (is_sensitive AND include_in_whatsapp)",
            name="ck_product_order_fields_sensitive_not_whatsapp",
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product_id",
            "key",
            name="uq_product_order_fields_product_id_key",
        ),
    )
    op.create_index(
        "ix_product_order_fields_product_sort",
        "product_order_fields",
        ["product_id", "sort_order", "id"],
        unique=False,
    )

    op.create_table(
        "product_order_field_options",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("field_id", sa.UUID(), nullable=False),
        sa.Column("value", sa.String(length=120), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("price_adjustment", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["field_id"],
            ["product_order_fields.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "field_id",
            "value",
            name="uq_product_order_field_options_field_id_value",
        ),
    )
    op.create_index(
        "ix_product_order_field_options_field_sort",
        "product_order_field_options",
        ["field_id", "sort_order", "id"],
        unique=False,
    )

    op.add_column(
        "orders",
        sa.Column("source", sa.String(length=40), nullable=False, server_default="web_checkout"),
    )
    op.add_column(
        "orders",
        sa.Column(
            "fulfillment_method",
            sa.String(length=40),
            nullable=False,
            server_default="seller_confirmation",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "whatsapp_handoff_status",
            sa.String(length=30),
            nullable=False,
            server_default="not_requested",
        ),
    )
    op.add_column(
        "orders",
        sa.Column("whatsapp_handoff_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column(
            "handoff_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    op.add_column(
        "order_items",
        sa.Column("product_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "order_items",
        sa.Column(
            "selected_options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "order_items",
        sa.Column(
            "configuration_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.execute(
        """
        UPDATE order_items AS oi
        SET product_type = COALESCE(p.product_type, 'physical')
        FROM products AS p
        WHERE p.id = oi.product_id
        """
    )
    op.execute(
        "UPDATE order_items SET product_type = 'physical' WHERE product_type IS NULL"
    )
    op.alter_column("order_items", "product_type", nullable=False, server_default="physical")


def downgrade() -> None:
    op.drop_column("order_items", "configuration_snapshot")
    op.drop_column("order_items", "selected_options")
    op.drop_column("order_items", "product_type")
    op.drop_column("orders", "handoff_metadata")
    op.drop_column("orders", "whatsapp_handoff_at")
    op.drop_column("orders", "whatsapp_handoff_status")
    op.drop_column("orders", "fulfillment_method")
    op.drop_column("orders", "source")
    op.drop_index(
        "ix_product_order_field_options_field_sort",
        table_name="product_order_field_options",
    )
    op.drop_table("product_order_field_options")
    op.drop_index(
        "ix_product_order_fields_product_sort",
        table_name="product_order_fields",
    )
    op.drop_table("product_order_fields")
    op.drop_column("products", "allowed_fulfillment_methods")
    op.drop_column("products", "default_fulfillment_method")
