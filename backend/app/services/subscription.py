import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from app.models import Store


def _to_aware(value):
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


def _normalize_optional_text(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    return normalized or None


def build_subscription_request_fingerprint(
    *,
    store_id: UUID,
    approved_by_user_id: UUID,
    plan_name: str | None,
    amount_paid: Decimal | None,
    extend_days: int,
    payment_method: str,
    payment_reference: str | None,
    note: str | None,
    mark_active: bool,
) -> str:
    """Return a deterministic fingerprint for a paid-subscription request."""

    canonical_payload = {
        "amount_paid": (
            format(
                amount_paid.quantize(
                    Decimal("0.01")
                ),
                "f",
            )
            if amount_paid is not None
            else None
        ),
        "approved_by_user_id": str(
            approved_by_user_id
        ),
        "extend_days": int(extend_days),
        "mark_active": bool(mark_active),
        "note": _normalize_optional_text(
            note
        ),
        "payment_method": (
            payment_method.lower().strip()
        ),
        "payment_reference": (
            _normalize_optional_text(
                payment_reference
            )
        ),
        "plan_name": (
            plan_name.lower().strip()
            if plan_name is not None
            else None
        ),
        "store_id": str(store_id),
    }

    encoded_payload = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(
        encoded_payload
    ).hexdigest()


def get_store_access_error(store: Store) -> str | None:
    if not store.is_active:
        return "This store is temporarily unavailable."

    if store.is_suspended:
        return "This store is temporarily unavailable."

    status = (store.subscription_status or "trial").lower()
    now = datetime.now(timezone.utc)

    if status == "suspended":
        return "This store is temporarily unavailable."

    if status == "expired":
        return "This store is temporarily unavailable."

    if status == "trial":
        trial_ends_at = _to_aware(store.trial_ends_at)

        if (
            trial_ends_at is None
            or trial_ends_at <= now
        ):
            return "This store is temporarily unavailable."

    if status == "active":
        subscription_ends_at = _to_aware(store.subscription_ends_at)

        if (
            subscription_ends_at is None
            or subscription_ends_at <= now
        ):
            return "This store is temporarily unavailable."

    return None


def get_subscription_status_after_unsuspension(
    store: Store,
    now: datetime | None = None,
) -> str:
    """Restore access state from valid dates without granting unpaid time."""

    current_status = (
        store.subscription_status
        or "expired"
    ).lower().strip()
    current_time = _to_aware(
        now
    ) or datetime.now(timezone.utc)
    subscription_end = _to_aware(
        store.subscription_ends_at
    )
    trial_end = _to_aware(
        store.trial_ends_at
    )

    has_paid_time = bool(
        subscription_end is not None
        and subscription_end > current_time
    )
    has_trial_time = bool(
        trial_end is not None
        and trial_end > current_time
    )

    if current_status == "active":
        return (
            "active"
            if has_paid_time
            else "expired"
        )

    if current_status == "trial":
        return (
            "trial"
            if has_trial_time
            else "expired"
        )

    if current_status == "suspended":
        if has_paid_time:
            return "active"

        if has_trial_time:
            return "trial"

    return "expired"


def get_subscription_extension_base(
    store: Store,
    now: datetime,
) -> datetime:
    """Return the date from which a paid extension should begin.

    Active paid time is preserved. When a seller converts during a valid
    trial, the paid period starts after the remaining trial so no time is
    lost. Expired or invalid dates fall back to ``now``.
    """

    current_time = _to_aware(now) or datetime.now(timezone.utc)
    candidates = [current_time]

    subscription_end = _to_aware(
        store.subscription_ends_at
    )

    if subscription_end and subscription_end > current_time:
        candidates.append(subscription_end)

    if (store.subscription_status or "trial").lower() == "trial":
        trial_end = _to_aware(store.trial_ends_at)

        if trial_end and trial_end > current_time:
            candidates.append(trial_end)

    return max(candidates)
