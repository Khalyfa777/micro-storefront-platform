from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
)

from app.utils.slug import (
    validate_canonical_slug,
    validate_store_name,
)


class StoreCreate(BaseModel):
    slug: str
    name: str
    bio: str | None = None
    logo_url: str | None = None
    banner_url: str | None = None
    whatsapp_number: str | None = None
    social_links: dict | None = None
    category: str | None = None
    theme: Any = None

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


class StoreUpdate(BaseModel):
    slug: str | None = None
    name: str | None = None
    bio: str | None = None
    logo_url: str | None = None
    banner_url: str | None = None
    whatsapp_number: str | None = None
    social_links: dict | None = None
    category: str | None = None
    theme: Any = None

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
