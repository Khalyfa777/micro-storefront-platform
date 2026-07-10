from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class OrderItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(ge=1, le=100)


class PublicOrderCreate(BaseModel):
    store_slug: str
    customer_name: str = Field(min_length=2, max_length=255)
    customer_phone: str = Field(min_length=7, max_length=30)
    customer_email: str | None = None
    delivery_address: str | None = None
    customer_note: str | None = None
    items: list[OrderItemCreate] = Field(min_length=1)


class OrderStatusUpdate(BaseModel):
    status: Literal["pending", "paid", "processing", "completed", "cancelled"]


class OrderItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: UUID
    store_id: UUID
    store_slug: str | None = None
    order_number: str
    status: str
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

    model_config = {"from_attributes": True}