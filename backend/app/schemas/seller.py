from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    field_validator,
)

from app.utils.slug import normalize_slug


class AdminSellerCreateRequest(BaseModel):
    full_name: str = Field(
        min_length=2,
        max_length=255,
    )
    email: EmailStr
    phone_number: str | None = Field(
        default=None,
        max_length=30,
    )
    store_name: str = Field(
        min_length=2,
        max_length=255,
    )
    store_slug: str = Field(
        min_length=3,
        max_length=100,
    )
    plan_name: str = Field(
        default="starter",
        min_length=1,
        max_length=50,
    )

    @field_validator(
        "full_name",
        "store_name",
        mode="before",
    )
    @classmethod
    def normalize_display_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value

        return " ".join(value.split())

    @field_validator(
        "phone_number",
        mode="before",
    )
    @classmethod
    def normalize_phone_number(
        cls,
        value: object,
    ) -> object:
        if value is None:
            return None

        if not isinstance(value, str):
            return value

        normalized = value.strip()

        return normalized or None

    @field_validator(
        "store_slug",
        mode="before",
    )
    @classmethod
    def normalize_store_slug(
        cls,
        value: object,
    ) -> object:
        if not isinstance(value, str):
            return value

        return normalize_slug(value)

    @field_validator(
        "plan_name",
        mode="before",
    )
    @classmethod
    def normalize_plan_name(
        cls,
        value: object,
    ) -> object:
        if not isinstance(value, str):
            return value

        return value.strip().lower()


class AdminSellerCreateResponse(BaseModel):
    seller_id: UUID
    store_id: UUID
    invitation_id: UUID

    full_name: str
    email: EmailStr
    phone_number: str | None = None

    store_name: str
    store_slug: str

    account_status: Literal["invited"]
    publication_status: Literal["draft"]

    plan_name: str
    subscription_status: Literal["trial"]
    monthly_fee: Decimal
    trial_ends_at: datetime

    invitation_expires_at: datetime
    invitation_url: str


class SellerInvitationTokenRequest(BaseModel):
    token: str = Field(
        min_length=20,
        max_length=512,
    )


class SellerInvitationAcceptRequest(
    SellerInvitationTokenRequest
):
    password: str = Field(
        min_length=8,
        max_length=128,
    )


class SellerInvitationValidationResponse(BaseModel):
    valid: Literal[True] = True

    invitation_id: UUID
    seller_id: UUID
    store_id: UUID

    full_name: str
    email: EmailStr

    store_name: str
    store_slug: str

    publication_status: Literal["draft"]
    expires_at: datetime


class SellerInvitationAcceptResponse(BaseModel):
    seller_id: UUID
    store_id: UUID

    account_status: Literal["active"]
    publication_status: Literal["draft"]

    accepted_at: datetime


class AdminSellerInvitationRegenerateRequest(BaseModel):
    current_invitation_id: UUID | None = None


class AdminSellerInvitationRegenerateResponse(BaseModel):
    seller_id: UUID
    store_id: UUID
    invitation_id: UUID

    invitation_expires_at: datetime
    invitation_url: str


class AdminSellerOnboardingCancelRequest(BaseModel):
    current_invitation_id: UUID


class AdminSellerOnboardingCancelResponse(BaseModel):
    seller_id: UUID
    invitation_id: UUID

    onboarding_status: Literal["cancelled"]
    revoked_at: datetime
