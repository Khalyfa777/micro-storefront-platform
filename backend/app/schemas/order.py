from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)

from app.services.order_tracking import (
    normalize_customer_phone,
    normalize_order_number,
)


class OrderItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(
        ge=1,
        le=100,
    )


class PublicOrderCreate(BaseModel):
    store_slug: str = Field(
        min_length=3,
        max_length=100,
    )
    customer_name: str = Field(
        min_length=2,
        max_length=255,
    )
    customer_phone: str = Field(
        min_length=7,
        max_length=30,
    )
    customer_email: str | None = Field(
        default=None,
        max_length=255,
    )
    delivery_address: str | None = Field(
        default=None,
        max_length=2000,
    )
    customer_note: str | None = Field(
        default=None,
        max_length=1000,
    )
    items: list[OrderItemCreate] = Field(
        min_length=1,
        max_length=100,
    )

    @field_validator("store_slug")
    @classmethod
    def normalize_store_slug(
        cls,
        value: str,
    ) -> str:
        return value.strip().lower()

    @field_validator("customer_name")
    @classmethod
    def normalize_customer_name(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if len(normalized) < 2:
            raise ValueError(
                "Customer name is required."
            )

        return normalized

    @field_validator("customer_phone")
    @classmethod
    def normalize_phone(
        cls,
        value: str,
    ) -> str:
        return normalize_customer_phone(
            value
        )

    @field_validator(
        "customer_email",
        "delivery_address",
        "customer_note",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        normalized = value.strip()

        return normalized or None


class PublicOrderTrackRequest(BaseModel):
    order_number: str = Field(
        min_length=3,
        max_length=30,
    )
    customer_phone: str = Field(
        min_length=7,
        max_length=30,
    )

    @field_validator("order_number")
    @classmethod
    def normalize_tracking_order_number(
        cls,
        value: str,
    ) -> str:
        return normalize_order_number(
            value
        )

    @field_validator("customer_phone")
    @classmethod
    def normalize_tracking_phone(
        cls,
        value: str,
    ) -> str:
        return normalize_customer_phone(
            value
        )


class OrderStatusUpdate(BaseModel):
    status: Literal[
        "pending",
        "paid",
        "processing",
        "completed",
        "cancelled",
    ]


class OrderItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal

    model_config = {
        "from_attributes": True
    }


class OrderResponse(BaseModel):
    id: UUID
    store_id: UUID
    store_slug: str | None = None
    order_number: str
    status: str
    payment_method: str | None = None
    inventory_deducted: bool = False
    is_oversold: bool = False
    customer_name: str
    customer_phone: str
    customer_email: str | None
    delivery_address: str | None
    customer_note: str | None

    subtotal: Decimal
    delivery_fee: Decimal
    total: Decimal
    currency: str

    items: list[OrderItemResponse]
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class PublicOrderTrackingItemResponse(
    BaseModel
):
    product_name: str
    quantity: int
    line_total: Decimal

    model_config = {
        "from_attributes": True
    }


class PublicOrderTrackingResponse(
    BaseModel
):
    order_number: str
    store_slug: str
    status: str
    total: Decimal
    currency: str
    items: list[
        PublicOrderTrackingItemResponse
    ]
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
