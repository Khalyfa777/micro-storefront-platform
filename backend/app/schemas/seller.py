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


class AdminSellerStoreSummary(BaseModel):
    id: UUID
    name: str
    slug: str

    publication_status: str
    is_active: bool
    is_suspended: bool

    plan_name: str
    subscription_status: str
    monthly_fee: Decimal

    trial_ends_at: datetime | None = None
    subscription_ends_at: datetime | None = None
    last_payment_at: datetime | None = None

    created_at: datetime
    updated_at: datetime


class AdminSellerInvitationSummary(BaseModel):
    id: UUID
    store_id: UUID

    status: Literal[
        "active",
        "expired",
        "accepted",
        "revoked",
    ]

    expires_at: datetime
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime


class AdminSellerListItem(BaseModel):
    seller_id: UUID

    full_name: str
    email: EmailStr
    phone_number: str | None = None

    account_status: Literal[
        "invited",
        "active",
        "suspended",
    ]

    setup_status: Literal[
        "pending",
        "completed",
        "cancelled",
    ]

    invitation_status: Literal[
        "active",
        "expired",
        "accepted",
        "revoked",
        "none",
    ]

    latest_invitation: (
        AdminSellerInvitationSummary | None
    ) = None

    store_count: int
    stores: list[AdminSellerStoreSummary]

    created_at: datetime
    updated_at: datetime


class AdminSellerListResponse(BaseModel):
    items: list[AdminSellerListItem]
    next_cursor: str | None = None
    has_more: bool


class AdminSellerAccountActionRequest(BaseModel):
    expected_updated_at: datetime

    reason: str | None = Field(
        default=None,
        max_length=500,
    )

    @field_validator(
        "reason",
        mode="before",
    )
    @classmethod
    def normalize_reason(
        cls,
        value: object,
    ) -> object:
        if value is None:
            return None

        if not isinstance(value, str):
            return value

        normalized = " ".join(value.split())

        return normalized or None


class AdminSellerAccountActionResponse(BaseModel):
    seller_id: UUID
    event_id: UUID

    account_status: Literal[
        "active",
        "suspended",
    ]

    is_active: bool
    is_verified: bool

    updated_at: datetime


class AdminSellerAccountEventSummary(BaseModel):
    id: UUID

    action: Literal[
        "suspend",
        "reactivate",
    ]

    previous_account_status: Literal[
        "active",
        "suspended",
    ]

    new_account_status: Literal[
        "active",
        "suspended",
    ]

    reason: str | None = None

    actor_user_id: UUID | None = None
    actor_email: EmailStr | None = None

    created_at: datetime


class AdminSellerSubscriptionPaymentSummary(BaseModel):
    id: UUID
    store_id: UUID
    plan_name: str
    amount: Decimal
    currency: str
    payment_method: str
    payment_reference: str | None = None
    note: str | None = None
    covered_days: int
    approved_by_email: EmailStr | None = None
    paid_at: datetime
    created_at: datetime


class AdminSellerDetailResponse(BaseModel):
    seller_id: UUID

    full_name: str
    email: EmailStr
    phone_number: str | None = None

    account_status: Literal[
        "invited",
        "active",
        "suspended",
    ]

    setup_status: Literal[
        "pending",
        "completed",
        "cancelled",
    ]

    invitation_status: Literal[
        "active",
        "expired",
        "accepted",
        "revoked",
        "none",
    ]

    is_active: bool
    is_verified: bool
    has_password: bool

    latest_invitation: (
        AdminSellerInvitationSummary | None
    ) = None

    invitation_count: int
    invitations: list[
        AdminSellerInvitationSummary
    ]

    store_count: int
    stores: list[AdminSellerStoreSummary]

    account_event_count: int
    account_events: list[
        AdminSellerAccountEventSummary
    ]

    subscription_payment_count: int
    subscription_payments: list[
        AdminSellerSubscriptionPaymentSummary
    ]

    created_at: datetime
    updated_at: datetime
