from datetime import datetime, timezone

from app.models import Store, User
from app.utils.slug import (
    validate_canonical_slug,
    validate_store_name,
)


def to_aware(
    value: datetime | None,
) -> datetime | None:
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc,
        )

    return value.astimezone(timezone.utc)


def to_iso(
    value: datetime | None,
) -> str | None:
    aware_value = to_aware(value)

    if aware_value is None:
        return None

    return aware_value.isoformat()


def normalized_publication_status(
    store: Store,
) -> str:
    return (
        store.publication_status
        or "draft"
    ).lower().strip()


def is_store_published(
    store: Store,
) -> bool:
    return (
        normalized_publication_status(store)
        == "published"
    )


def timestamps_match(
    current: datetime,
    expected: datetime,
) -> bool:
    return (
        to_aware(current)
        == to_aware(expected)
    )


def seller_onboarding_complete(
    owner: User | None,
) -> bool:
    return bool(
        owner is not None
        and owner.role == "merchant"
        and owner.is_verified
        and owner.password_hash
    )


def store_name_is_valid(
    value: str | None,
) -> bool:
    try:
        validate_store_name(
            value or ""
        )
    except (TypeError, ValueError):
        return False

    return True


def store_slug_is_valid(
    value: str | None,
) -> bool:
    try:
        validate_canonical_slug(
            value or ""
        )
    except (TypeError, ValueError):
        return False

    return True


def get_admin_publish_blockers(
    *,
    store: Store,
    owner: User | None,
    active_product_count: int,
    now: datetime | None = None,
) -> list[str]:
    current_time = (
        to_aware(now)
        if now is not None
        else datetime.now(timezone.utc)
    )

    if current_time is None:
        current_time = datetime.now(
            timezone.utc,
        )

    blockers: list[str] = []

    if not seller_onboarding_complete(owner):
        blockers.append(
            "Seller onboarding is incomplete."
        )

    if not (store.name or "").strip():
        blockers.append(
            "Store name is required."
        )
    elif not store_name_is_valid(
        store.name
    ):
        blockers.append(
            "Store name is invalid."
        )

    if not (store.slug or "").strip():
        blockers.append(
            "Store slug is required."
        )
    elif not store_slug_is_valid(
        store.slug
    ):
        blockers.append(
            "Store slug is invalid."
        )

    if not store.is_active:
        blockers.append(
            "Store is operationally inactive."
        )

    if store.is_suspended:
        blockers.append(
            "Store is suspended."
        )

    if active_product_count < 1:
        blockers.append(
            "At least one active product is required."
        )

    subscription_status = (
        store.subscription_status
        or ""
    ).lower().strip()

    if subscription_status == "trial":
        trial_ends_at = to_aware(
            store.trial_ends_at
        )

        if (
            trial_ends_at is None
            or trial_ends_at <= current_time
        ):
            blockers.append(
                "The store trial has expired."
            )

    elif subscription_status == "active":
        subscription_ends_at = to_aware(
            store.subscription_ends_at
        )

        if (
            subscription_ends_at is None
            or subscription_ends_at
            <= current_time
        ):
            blockers.append(
                "The store subscription has expired."
            )

    else:
        blockers.append(
            "A valid trial or active subscription is required."
        )

    return blockers


def build_publication_readiness_snapshot(
    *,
    store: Store,
    owner: User | None,
    active_product_count: int,
    blockers: list[str],
    evaluated_at: datetime,
) -> dict[str, object]:
    return {
        "evaluated_at": to_iso(
            evaluated_at
        ),
        "publication_status": (
            normalized_publication_status(store)
        ),
        "seller_onboarding_complete": (
            seller_onboarding_complete(owner)
        ),
        "store_name_present": bool(
            (store.name or "").strip()
        ),
        "store_name_valid": (
            store_name_is_valid(
                store.name
            )
        ),
        "store_slug_present": bool(
            (store.slug or "").strip()
        ),
        "store_slug_valid": (
            store_slug_is_valid(
                store.slug
            )
        ),
        "store_is_active": bool(
            store.is_active
        ),
        "store_is_suspended": bool(
            store.is_suspended
        ),
        "subscription_status": (
            store.subscription_status
            or ""
        ).lower().strip(),
        "trial_ends_at": to_iso(
            store.trial_ends_at
        ),
        "subscription_ends_at": to_iso(
            store.subscription_ends_at
        ),
        "active_product_count": int(
            active_product_count
        ),
        "publish_ready": not blockers,
        "blockers": list(blockers),
    }
