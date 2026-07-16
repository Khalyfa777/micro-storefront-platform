from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.utils.phone import (
    normalize_ghana_whatsapp_number,
)
from app.utils.slug import (
    validate_canonical_slug,
    validate_store_name,
)


class StoreCreate(BaseModel):
    slug: str
    name: str
    bio: str | None = Field(default=None, max_length=2000)
    logo_url: str | None = Field(default=None, max_length=500)
    banner_url: str | None = Field(default=None, max_length=500)
    whatsapp_number: str | None = None
    social_links: dict[str, str] | None = None
    category: str | None = Field(default=None, max_length=50)
    theme: str = Field(default="default", max_length=50)

    @field_validator("slug")
    @classmethod
    def validate_slug(
        cls,
        value: str,
    ) -> str:
        return validate_canonical_slug(
            value
        )

    @field_validator("name")
    @classmethod
    def validate_name(
        cls,
        value: str,
    ) -> str:
        return validate_store_name(value)

    @field_validator(
        "bio",
        "logo_url",
        "banner_url",
        "category",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        if value is None or not isinstance(value, str):
            return value

        normalized = value.strip()
        return normalized or None

    @field_validator("whatsapp_number", mode="before")
    @classmethod
    def validate_whatsapp_number(
        cls,
        value: object,
    ) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise ValueError(
                "WhatsApp number must be text."
            )

        return normalize_ghana_whatsapp_number(value)


class StoreUpdate(BaseModel):
    slug: str | None = None
    name: str | None = None
    bio: str | None = Field(default=None, max_length=2000)
    logo_url: str | None = Field(default=None, max_length=500)
    banner_url: str | None = Field(default=None, max_length=500)
    whatsapp_number: str | None = None
    social_links: dict[str, str] | None = None
    category: str | None = Field(default=None, max_length=50)
    theme: str | None = Field(default=None, max_length=50)

    @field_validator("slug")
    @classmethod
    def validate_slug(
        cls,
        value: str | None,
    ) -> str:
        if value is None:
            raise ValueError(
                "Store slug cannot be null."
            )

        return validate_canonical_slug(
            value
        )

    @field_validator("name")
    @classmethod
    def validate_name(
        cls,
        value: str | None,
    ) -> str:
        if value is None:
            raise ValueError(
                "Store name cannot be null."
            )

        return validate_store_name(value)

    @field_validator(
        "bio",
        "logo_url",
        "banner_url",
        "category",
        "theme",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: object,
    ) -> object:
        if value is None or not isinstance(value, str):
            return value

        normalized = value.strip()
        return normalized or None

    @field_validator("whatsapp_number", mode="before")
    @classmethod
    def validate_whatsapp_number(
        cls,
        value: object,
    ) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise ValueError(
                "WhatsApp number must be text."
            )

        return normalize_ghana_whatsapp_number(value)


class StoreResponse(BaseModel):
    id: UUID
    owner_id: UUID
    slug: str
    name: str
    bio: str | None = None
    logo_url: str | None = None
    banner_url: str | None = None
    whatsapp_number: str | None = None
    social_links: dict | None = None
    category: str | None = None
    theme: Any = None
    is_active: bool
    is_suspended: bool
    publication_status: str = "draft"
    plan_name: str = "starter"
    subscription_status: str = "trial"
    trial_ends_at: datetime | None = None
    subscription_ends_at: datetime | None = None
    last_payment_at: datetime | None = None
    monthly_fee: Decimal = Decimal("0.00")
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(
        from_attributes=True
    )


class StorePublicResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    bio: str | None = None
    whatsapp_number: str | None = None
    logo_url: str | None = None
    banner_url: str | None = None
    category: str | None = None
    can_receive_online_payments: bool = False

    model_config = ConfigDict(
        from_attributes=True
    )
