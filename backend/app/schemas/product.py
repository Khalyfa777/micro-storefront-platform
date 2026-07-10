from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    image_url: str | None = None
    product_type: str = "physical"
    price: Decimal = Field(gt=0)
    stock_quantity: int | None = Field(default=0, ge=0)
    is_active: bool = True
    is_featured: bool = False


class ProductUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    image_url: str | None = None
    product_type: str | None = None
    price: Decimal | None = Field(default=None, gt=0)
    stock_quantity: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    is_featured: bool | None = None


class ProductResponse(BaseModel):
    id: UUID
    store_id: UUID
    name: str
    slug: str
    description: str | None = None
    image_url: str | None = None
    product_type: str
    price: Decimal = Field(gt=0)
    stock_quantity: int | None = Field(default=None, ge=0)
    is_active: bool
    is_featured: bool

    class Config:
        from_attributes = True
