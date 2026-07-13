import pytest

from app.services.order_idempotency import (
    build_order_request_fingerprint,
    normalize_order_idempotency_key,
)


VALID_KEY = (
    "checkout-order-"
    "0123456789abcdef"
)


def make_payload(
    *,
    quantity: int = 1,
    items=None,
):
    return {
        "store_slug": "demo-store",
        "customer_name": "Test Customer",
        "customer_phone": "233241234567",
        "customer_email": None,
        "delivery_address": None,
        "customer_note": None,
        "items": (
            items
            if items is not None
            else [
                {
                    "product_id": (
                        "00000000-0000-0000-"
                        "0000-000000000001"
                    ),
                    "quantity": quantity,
                }
            ]
        ),
    }


def test_idempotency_key_is_trimmed():
    assert (
        normalize_order_idempotency_key(
            f"  {VALID_KEY}  "
        )
        == VALID_KEY
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "too-short",
        "contains spaces 123456789",
        "invalid/key/0123456789",
        "x" * 129,
    ],
)
def test_invalid_idempotency_keys_rejected(
    value,
):
    with pytest.raises(ValueError):
        normalize_order_idempotency_key(
            value
        )


def test_fingerprint_is_stable():
    payload = make_payload()

    first = build_order_request_fingerprint(
        payload
    )

    second = build_order_request_fingerprint(
        dict(payload)
    )

    assert first == second
    assert len(first) == 64


def test_item_order_does_not_change_fingerprint():
    first_item = {
        "product_id": (
            "00000000-0000-0000-"
            "0000-000000000001"
        ),
        "quantity": 1,
    }

    second_item = {
        "product_id": (
            "00000000-0000-0000-"
            "0000-000000000002"
        ),
        "quantity": 2,
    }

    first = build_order_request_fingerprint(
        make_payload(
            items=[
                first_item,
                second_item,
            ]
        )
    )

    second = build_order_request_fingerprint(
        make_payload(
            items=[
                second_item,
                first_item,
            ]
        )
    )

    assert first == second


def test_changed_payload_changes_fingerprint():
    first = build_order_request_fingerprint(
        make_payload(quantity=1)
    )

    second = build_order_request_fingerprint(
        make_payload(quantity=2)
    )

    assert first != second


def test_fingerprint_does_not_expose_phone():
    payload = make_payload()

    fingerprint = (
        build_order_request_fingerprint(
            payload
        )
    )

    assert (
        payload["customer_phone"]
        not in fingerprint
    )
