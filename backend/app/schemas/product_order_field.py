
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_serializer,
    model_validator,
)

from app.services.conversational_ordering import (
    validate_order_field_definition,
    validate_order_field_definitions,
)


OrderFieldType = Literal[
    "text",
    "textarea",
    "select",
    "radio",
    "checkbox",
    "number",
    "date",
    "time",
    "datetime",
    "phone",
    "email",
]


class OrderFieldValidationRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_length: int | None = Field(
        default=None,
        strict=True,
        ge=0,
        le=2000,
    )
    max_length: int | None = Field(
        default=None,
        strict=True,
        ge=1,
        le=2000,
    )
    min: Decimal | None = None
    max: Decimal | None = None

    @field_validator("min", "max")
    @classmethod
    def require_finite_number(
        cls,
        value: Decimal | None,
    ) -> Decimal | None:
        if value is not None and not value.is_finite():
            raise ValueError(
                "Number validation limits must be finite."
            )
        return value

    @model_validator(mode="after")
    def enforce_rule_order(self):
        if (
            self.min_length is not None
            and self.max_length is not None
            and self.min_length > self.max_length
        ):
            raise ValueError(
                "min_length cannot exceed max_length."
            )

        if (
            self.min is not None
            and self.max is not None
            and self.min > self.max
        ):
            raise ValueError(
                "Minimum cannot exceed maximum."
            )

        return self

    @model_serializer
    def serialize_rules(self):
        serialized: dict[str, int | Decimal] = {}

        if self.min_length is not None:
            serialized["min_length"] = self.min_length

        if self.max_length is not None:
            serialized["max_length"] = self.max_length

        if self.min is not None:
            serialized["min"] = self.min

        if self.max is not None:
            serialized["max"] = self.max

        return serialized


class ProductOrderFieldOptionCreate(BaseModel):
    value: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=120)
    price_adjustment: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=10000)

    @field_validator("value", "label")
    @classmethod
    def normalize_option_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Option values and labels cannot be blank.")
        return normalized

    @field_validator("price_adjustment")
    @classmethod
    def require_non_negative_finite_price_adjustment(
        cls,
        value: Decimal,
    ) -> Decimal:
        if not value.is_finite():
            raise ValueError(
                "Extra charge must be a finite number."
            )

        if value < 0:
            raise ValueError(
                "Extra charge must be zero or more."
            )

        return value


class ProductOrderFieldCreate(BaseModel):
    key: str = Field(min_length=1, max_length=50)
    label: str = Field(min_length=1, max_length=120)
    field_type: OrderFieldType
    placeholder: str | None = Field(default=None, max_length=255)
    help_text: str | None = Field(default=None, max_length=1000)
    is_required: bool = False
    is_sensitive: bool = False
    include_in_whatsapp: bool = True
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=10000)
    validation_rules: OrderFieldValidationRules = Field(
        default_factory=OrderFieldValidationRules
    )
    options: list[ProductOrderFieldOptionCreate] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def enforce_order_field_policy(self):
        validate_order_field_definition(self.model_dump())
        return self


class ProductOrderFieldsReplace(BaseModel):
    fields: list[ProductOrderFieldCreate] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def enforce_unique_fields(self):
        validate_order_field_definitions(
            field.model_dump() for field in self.fields
        )
        return self


class ProductOrderFieldOptionResponse(BaseModel):
    id: UUID
    value: str
    label: str
    price_adjustment: Decimal
    is_active: bool
    sort_order: int
    model_config = ConfigDict(from_attributes=True)


class ProductOrderFieldResponse(BaseModel):
    id: UUID
    product_id: UUID
    key: str
    label: str
    field_type: str
    placeholder: str | None = None
    help_text: str | None = None
    is_required: bool
    is_sensitive: bool
    include_in_whatsapp: bool
    is_active: bool
    sort_order: int
    validation_rules: dict
    options: list[ProductOrderFieldOptionResponse]
    model_config = ConfigDict(from_attributes=True)
