
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.product_order_field import (
    ProductOrderFieldCreate,
    ProductOrderFieldResponse,
)
from app.services.conversational_ordering import (
    normalize_fulfillment_configuration,
    validate_order_field_definitions,
)


ProductType = Literal[
    "physical",
    "digital",
    "subscription",
    "service",
    "food",
    "booking",
    "custom",
]

FulfillmentMethod = Literal[
    "delivery",
    "pickup",
    "digital_delivery",
    "activation",
    "appointment",
    "on_site_service",
    "remote_service",
    "reservation",
    "seller_confirmation",
]


class ProductCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    image_url: str | None = None
    product_type: ProductType = "physical"
    default_fulfillment_method: FulfillmentMethod | None = None
    allowed_fulfillment_methods: list[FulfillmentMethod] | None = None
    price: Decimal = Field(gt=0)
    stock_quantity: int | None = Field(default=0, ge=0)
    is_active: bool = True
    is_featured: bool = False
    order_fields: list[ProductOrderFieldCreate] = Field(
        default_factory=list,
        max_length=50,
    )

    @model_validator(mode="after")
    def normalize_fulfillment(self):
        default_method, allowed_methods = normalize_fulfillment_configuration(
            self.product_type,
            self.default_fulfillment_method,
            self.allowed_fulfillment_methods,
        )
        self.default_fulfillment_method = default_method
        self.allowed_fulfillment_methods = allowed_methods
        validate_order_field_definitions(
            field.model_dump() for field in self.order_fields
        )
        return self


class ProductUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    image_url: str | None = None
    product_type: ProductType | None = None
    default_fulfillment_method: FulfillmentMethod | None = None
    allowed_fulfillment_methods: list[FulfillmentMethod] | None = None
    price: Decimal | None = Field(default=None, gt=0)
    stock_quantity: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    is_featured: bool | None = None
    order_fields: list[ProductOrderFieldCreate] | None = Field(
        default=None,
        max_length=50,
    )

    @model_validator(mode="after")
    def validate_order_fields(self):
        if self.order_fields is not None:
            validate_order_field_definitions(
                field.model_dump() for field in self.order_fields
            )
        return self


class ProductResponse(BaseModel):
    id: UUID
    store_id: UUID
    name: str
    slug: str
    description: str | None = None
    image_url: str | None = None
    product_type: str
    default_fulfillment_method: str = "seller_confirmation"
    allowed_fulfillment_methods: list[str] = Field(
        default_factory=lambda: ["seller_confirmation"]
    )
    price: Decimal = Field(gt=0)
    stock_quantity: int | None = Field(default=None, ge=0)
    is_active: bool
    is_featured: bool
    order_fields: list[ProductOrderFieldResponse] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)
