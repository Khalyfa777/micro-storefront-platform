import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import HTTPException, status

from app.models import SellerInvitation, User


SellerAccountStatus = Literal[
    "invited",
    "active",
    "suspended",
]

SellerInvitationStatus = Literal[
    "active",
    "expired",
    "accepted",
    "revoked",
    "none",
]

SellerSetupStatus = Literal[
    "pending",
    "completed",
    "cancelled",
]

CURSOR_VERSION = 1
MAX_CURSOR_LENGTH = 512


@dataclass(frozen=True)
class SellerListCursor:
    created_at: datetime
    seller_id: UUID


def _aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def encode_seller_cursor(
    created_at: datetime,
    seller_id: UUID,
) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "created_at": _aware_datetime(
            created_at
        ).isoformat(timespec="microseconds"),
        "id": str(seller_id),
    }

    serialized = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    return (
        base64.urlsafe_b64encode(serialized)
        .decode("ascii")
        .rstrip("=")
    )


def decode_seller_cursor(
    value: str,
) -> SellerListCursor:
    cursor = value.strip()

    if (
        not cursor
        or len(cursor) > MAX_CURSOR_LENGTH
    ):
        raise _invalid_cursor()

    padding = "=" * (-len(cursor) % 4)

    try:
        decoded = base64.b64decode(
            (cursor + padding).encode("ascii"),
            altchars=b"-_",
            validate=True,
        )

        payload = json.loads(
            decoded.decode("utf-8")
        )

        if not isinstance(payload, dict):
            raise ValueError

        if set(payload) != {
            "v",
            "created_at",
            "id",
        }:
            raise ValueError

        if payload["v"] != CURSOR_VERSION:
            raise ValueError

        created_at = datetime.fromisoformat(
            payload["created_at"]
        )

        if created_at.tzinfo is None:
            raise ValueError

        seller_id = UUID(payload["id"])

    except (
        UnicodeEncodeError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as exc:
        raise _invalid_cursor() from exc

    return SellerListCursor(
        created_at=_aware_datetime(created_at),
        seller_id=seller_id,
    )


def _invalid_cursor() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid seller pagination cursor.",
    )


def derive_account_status(
    seller: User,
) -> SellerAccountStatus:
    if (
        seller.is_active is False
        and seller.is_verified is False
    ):
        return "invited"

    if (
        seller.is_active is True
        and seller.is_verified is True
    ):
        return "active"

    if (
        seller.is_active is False
        and seller.is_verified is True
    ):
        return "suspended"

    raise ValueError(
        "Seller account state is inconsistent."
    )


def derive_invitation_status(
    invitation: SellerInvitation | None,
    now: datetime,
) -> SellerInvitationStatus:
    if invitation is None:
        return "none"

    if invitation.accepted_at is not None:
        return "accepted"

    if invitation.revoked_at is not None:
        return "revoked"

    if (
        _aware_datetime(invitation.expires_at)
        <= _aware_datetime(now)
    ):
        return "expired"

    return "active"


def derive_setup_status(
    seller: User,
    invitation_status: SellerInvitationStatus,
) -> SellerSetupStatus:
    if (
        seller.password_hash
        and seller.is_verified is True
    ):
        return "completed"

    if invitation_status == "revoked":
        return "cancelled"

    return "pending"
