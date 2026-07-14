from datetime import datetime, timezone

from app.models import Store


def _to_aware(value):
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


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

        if trial_ends_at and trial_ends_at <= now:
            return "This store is temporarily unavailable."

    if status == "active":
        subscription_ends_at = _to_aware(store.subscription_ends_at)

        if subscription_ends_at and subscription_ends_at <= now:
            return "This store is temporarily unavailable."

    return None

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
