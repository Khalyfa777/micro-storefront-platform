import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, DateTime, ForeignKey, Numeric, Integer, Boolean, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(1000))


    product_type: Mapped[str] = mapped_column(String(50), default="physical", nullable=False)
    default_fulfillment_method: Mapped[str] = mapped_column(
        String(40),
        default="seller_confirmation",
        nullable=False,
    )
    allowed_fulfillment_methods: Mapped[list[str]] = mapped_column(
        JSONB,
        default=lambda: ["seller_confirmation"],
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    stock_quantity: Mapped[int | None] = mapped_column(Integer)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


    store: Mapped["Store"] = relationship("Store", back_populates="products")
    order_fields = relationship(
        "ProductOrderField",
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ProductOrderField.sort_order, ProductOrderField.id",
        lazy="selectin",
    )
