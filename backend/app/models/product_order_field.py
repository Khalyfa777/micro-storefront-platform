
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ProductOrderField(Base):
    __tablename__ = "product_order_fields"
    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "key",
            name="uq_product_order_fields_product_id_key",
        ),
        CheckConstraint(
            "key ~ '^[a-z][a-z0-9_]{0,49}$'",
            name="ck_product_order_fields_key_format",
        ),
        CheckConstraint(
            "NOT (is_sensitive AND include_in_whatsapp)",
            name="ck_product_order_fields_sensitive_not_whatsapp",
        ),
        Index(
            "ix_product_order_fields_product_sort",
            "product_id",
            "sort_order",
            "id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    field_type: Mapped[str] = mapped_column(String(30), nullable=False)
    placeholder: Mapped[str | None] = mapped_column(String(255))
    help_text: Mapped[str | None] = mapped_column(Text)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    include_in_whatsapp: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    validation_rules: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    product = relationship("Product", back_populates="order_fields")
    options = relationship(
        "ProductOrderFieldOption",
        back_populates="field",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ProductOrderFieldOption.sort_order, ProductOrderFieldOption.id",
        lazy="selectin",
    )


class ProductOrderFieldOption(Base):
    __tablename__ = "product_order_field_options"
    __table_args__ = (
        UniqueConstraint(
            "field_id",
            "value",
            name="uq_product_order_field_options_field_id_value",
        ),
        CheckConstraint(
            "price_adjustment >= 0 "
            "AND price_adjustment < 'Infinity'::numeric",
            name=(
                "ck_product_order_option_price_"
                "non_negative_finite"
            ),
        ),
        Index(
            "ix_product_order_field_options_field_sort",
            "field_id",
            "sort_order",
            "id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    field_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_order_fields.id", ondelete="CASCADE"),
        nullable=False,
    )
    value: Mapped[str] = mapped_column(String(120), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    price_adjustment: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    field = relationship("ProductOrderField", back_populates="options")
