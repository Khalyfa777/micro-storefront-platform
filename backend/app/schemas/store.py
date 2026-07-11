from decimal import Decimal
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
    plan_name: str = "starter"
    subscription_status: str = "trial"
    trial_ends_at: datetime | None = None
    subscription_ends_at: datetime | None = None
    last_payment_at: datetime | None = None
    monthly_fee: Decimal = Decimal("0.00")
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class StorePublicResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    bio: str | None = None
    whatsapp_number: str | None = None
    logo_url: str | None = None
    banner_url: str | None = None
    category: str | None = None

    model_config = ConfigDict(from_attributes=True)
