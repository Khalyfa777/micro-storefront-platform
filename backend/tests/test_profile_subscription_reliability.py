from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.store import StoreUpdate
from app.services.subscription import (
    get_subscription_extension_base,
)


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("0544494613", "233544494613"),
        ("233544494613", "233544494613"),
        ("+233 54 449 4613", "233544494613"),
        ("", None),
        ("   ", None),
    ],
)
def test_store_update_normalizes_ghana_whatsapp_number(
    raw_value,
    expected,
):
    payload = StoreUpdate(
        whatsapp_number=raw_value,
    )

    assert payload.whatsapp_number == expected


@pytest.mark.parametrize(
    "raw_value",
    [
        "0557657643/0544494613",
        "0544494613,0557657643",
        "05444ABC13",
        "+233544494613+",
        "544494613",
    ],
)
def test_store_update_rejects_invalid_or_multiple_numbers(
    raw_value,
):
    with pytest.raises(ValidationError):
        StoreUpdate(
            whatsapp_number=raw_value,
        )


def test_trial_conversion_preserves_remaining_trial_time():
    now = datetime(2026, 7, 13, tzinfo=timezone.utc)
    trial_end = now + timedelta(days=14)
    store = SimpleNamespace(
        subscription_status="trial",
        trial_ends_at=trial_end,
        subscription_ends_at=None,
    )

    assert get_subscription_extension_base(
        store,
        now,
    ) == trial_end


def test_paid_renewal_preserves_remaining_paid_time():
    now = datetime(2026, 7, 13, tzinfo=timezone.utc)
    subscription_end = now + timedelta(days=9)
    store = SimpleNamespace(
        subscription_status="active",
        trial_ends_at=now + timedelta(days=30),
        subscription_ends_at=subscription_end,
    )

    assert get_subscription_extension_base(
        store,
        now,
    ) == subscription_end


def test_expired_subscription_extension_starts_now():
    now = datetime(2026, 7, 13, tzinfo=timezone.utc)
    store = SimpleNamespace(
        subscription_status="expired",
        trial_ends_at=now - timedelta(days=20),
        subscription_ends_at=now - timedelta(days=1),
    )

    assert get_subscription_extension_base(
        store,
        now,
    ) == now
