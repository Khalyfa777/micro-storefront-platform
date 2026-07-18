import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal, Mapping
from uuid import UUID

from pydantic import EmailStr
from pydantic import (
    BaseModel,
    Field,
    ValidationInfo,
    field_validator,
)

from app.services.order_tracking import (
    normalize_customer_phone,
    normalize_order_number,
)


_ORDER_OPTION_KEY_PATTERN = re.compile(
    r"^[a-z][a-z0-9_]{0,49}$"
)
_MAX_SELECTED_OPTIONS = 50
_MAX_SELECTED_OPTION_TEXT_LENGTH = 2000


def _normalize_selected_options(
    value: object,
) -> dict[str, str | bool]:
    if value is None:
        return {}

    if not isinstance(value, Mapping):
        raise ValueError(
            "Selected options must be an object."
        )

    if len(value) > _MAX_SELECTED_OPTIONS:
        raise ValueError(
            "An order item may include at most "
            f"{_MAX_SELECTED_OPTIONS} selected options."
        )

    normalized: dict[str, str | bool] = {}

    for raw_key, raw_value in value.items():
        if not isinstance(raw_key, str):
            raise ValueError(
                "Selected option names must be text."
            )

        key = raw_key.strip().lower()

        if _ORDER_OPTION_KEY_PATTERN.fullmatch(key) is None:
            raise ValueError(
                "Selected option names must start with a letter "
                "and use only lowercase letters, numbers, or underscores."
            )

        if key in normalized:
            raise ValueError(
                f"Duplicate selected option: {key}."
            )

        if raw_value is None:
            continue

        if isinstance(raw_value, bool):
            normalized[key] = raw_value
            continue

        if isinstance(raw_value, str):
            text = raw_value.strip()

            if not text:
                continue

            if len(text) > _MAX_SELECTED_OPTION_TEXT_LENGTH:
                raise ValueError(
                    f"Selected option {key} is too long."
                )

            normalized[key] = text
            continue

        if isinstance(raw_value, (int, float, Decimal)):
            numeric_text = str(raw_value)

            if len(numeric_text) > 128:
                raise ValueError(
                    f"Selected option {key} is too long."
                )

            try:
                number = Decimal(numeric_text)
            except (InvalidOperation, TypeError, ValueError) as error:
                raise ValueError(
                    f"Selected option {key} must be a valid number."
                ) from error

            if not number.is_finite():
                raise ValueError(
                    f"Selected option {key} must be finite."
                )

            rendered_number = format(number, "f")

            if len(rendered_number) > _MAX_SELECTED_OPTION_TEXT_LENGTH:
                raise ValueError(
                    f"Selected option {key} is too long."
                )

            normalized[key] = rendered_number
            continue

        raise ValueError(
            f"Selected option {key} must be text, a number, "
            "or a yes/no value."
        )

    return normalized


class OrderItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(
        ge=1,
        le=100,
    )
    selected_options: dict[str, str | bool] = Field(
        default_factory=dict,
        max_length=_MAX_SELECTED_OPTIONS,
    )

    @field_validator(
        "selected_options",
        mode="before",
    )
    @classmethod
    def normalize_selected_options(
        cls,
        value: object,
    ) -> dict[str, str | bool]:
        return _normalize_selected_options(value)


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
    customer_email: EmailStr | None = Field(
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
    fulfillment_method: str | None = Field(default=None, max_length=40)
    handoff_channel: Literal["none", "whatsapp"] = "none"
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
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
        info: ValidationInfo,
    ) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            labels = {
                "customer_email": "Customer email",
                "delivery_address": "Delivery location",
                "customer_note": "Customer note",
            }
            label = labels.get(
                info.field_name,
                "This value",
            )
            raise ValueError(
                f"{label} must be text."
            )

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
    product_type: str = "physical"
    selected_options: dict[str, object] = Field(default_factory=dict)
    configuration_snapshot: list[dict[str, object]] = Field(default_factory=list)
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
    source: str = "web_checkout"
    fulfillment_method: str = "seller_confirmation"
    whatsapp_handoff_status: str = "not_requested"
    whatsapp_handoff_at: datetime | None = None
    handoff_metadata: dict[str, object] = Field(default_factory=dict)
    whatsapp_message: str | None = None
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
