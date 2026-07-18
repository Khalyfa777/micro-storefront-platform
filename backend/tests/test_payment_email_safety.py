from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import app.api.v1.payments as payments_module
from app.api.v1.payments import (
    PAYMENT_EMAIL_REQUIRED_DETAIL,
    PAYMENT_LINK_EMAIL_MISMATCH_DETAIL,
    PAYMENT_LINK_UNSAFE_DETAIL,
    initialize_payment,
    normalize_payment_email,
)
from app.models import Transaction
from app.schemas.order import PublicOrderCreate
from app.schemas.payment import PaymentInitializeRequest


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeSession:
    def __init__(self, values):
        self.values = list(values)
        self.added = []
        self.commit_count = 0

    async def execute(self, statement):
        del statement

        if not self.values:
            raise AssertionError(
                "Unexpected database query."
            )

        return FakeResult(
            self.values.pop(0)
        )

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commit_count += 1


class FakeResponse:
    status_code = 200

    def json(self):
        return {
            "status": True,
            "message": "Authorization URL created",
            "data": {
                "authorization_url": (
                    "https://checkout.paystack.test/example"
                ),
                "access_code": "access-code",
            },
        }


class FakeAsyncClient:
    captured_payload = None

    def __init__(self, *args, **kwargs):
        del args, kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        del exc_type, exc, traceback

    async def post(
        self,
        url,
        headers,
        json,
    ):
        del url, headers
        type(self).captured_payload = json
        return FakeResponse()


def build_order(
    *,
    customer_email=None,
):
    return SimpleNamespace(
        id=uuid4(),
        order_number="SP-TEST-0001",
        status="pending",
        store_id=uuid4(),
        customer_email=customer_email,
        total=Decimal("25.00"),
        currency="GHS",
        items=[],
    )


def build_store(order):
    return SimpleNamespace(
        id=order.store_id,
    )


async def allow_online_payments(
    db,
    store,
):
    del db, store


def configure_payment_dependencies(
    monkeypatch,
):
    monkeypatch.setattr(
        payments_module,
        "get_paystack_secret_key",
        lambda: "sk_test_secret",
    )
    monkeypatch.setattr(
        payments_module,
        "ensure_plan_allows_online_payments",
        allow_online_payments,
    )


def test_payment_request_rejects_invalid_email():
    with pytest.raises(ValidationError):
        PaymentInitializeRequest(
            order_id=uuid4(),
            customer_email="not-an-email",
        )


def test_public_order_email_is_optional_but_validated():
    without_email = PublicOrderCreate(
        store_slug="test-store",
        customer_name="Test Customer",
        customer_phone="+233200000000",
        customer_email="   ",
        items=[
            {
                "product_id": uuid4(),
                "quantity": 1,
                "selected_options": {},
            }
        ],
    )

    assert without_email.customer_email is None

    with pytest.raises(ValidationError):
        PublicOrderCreate(
            store_slug="test-store",
            customer_name="Test Customer",
            customer_phone="+233200000000",
            customer_email="not-an-email",
            items=[
                {
                    "product_id": uuid4(),
                    "quantity": 1,
                    "selected_options": {},
                }
            ],
        )


def test_normalize_payment_email_trims_and_normalizes():
    assert normalize_payment_email(
        "  Customer@Example.COM  "
    ) == "customer@example.com"


@pytest.mark.asyncio
async def test_initialize_requires_email_before_transaction_lookup(
    monkeypatch,
):
    configure_payment_dependencies(monkeypatch)

    order = build_order()
    db = FakeSession(
        [
            order,
            build_store(order),
        ]
    )

    with pytest.raises(HTTPException) as captured:
        await initialize_payment(
            payload=PaymentInitializeRequest(
                order_id=order.id,
            ),
            db=db,
        )

    assert captured.value.status_code == 422
    assert (
        captured.value.detail
        == PAYMENT_EMAIL_REQUIRED_DETAIL
    )
    assert db.values == []


@pytest.mark.asyncio
async def test_initialize_blocks_legacy_pending_link_without_payer_email(
    monkeypatch,
):
    configure_payment_dependencies(monkeypatch)

    order = build_order(
        customer_email="customer@example.com"
    )
    legacy_transaction = SimpleNamespace(
        authorization_url=(
            "https://checkout.paystack.test/legacy"
        ),
        access_code="legacy-access",
        provider_reference="MSF-LEGACY",
        payer_email=None,
    )
    db = FakeSession(
        [
            order,
            build_store(order),
            legacy_transaction,
        ]
    )

    with pytest.raises(HTTPException) as captured:
        await initialize_payment(
            payload=PaymentInitializeRequest(
                order_id=order.id,
                customer_email="customer@example.com",
            ),
            db=db,
        )

    assert captured.value.status_code == 409
    assert (
        captured.value.detail
        == PAYMENT_LINK_UNSAFE_DETAIL
    )


@pytest.mark.asyncio
async def test_initialize_reuses_only_matching_recorded_email(
    monkeypatch,
):
    configure_payment_dependencies(monkeypatch)

    order = build_order(
        customer_email="customer@example.com"
    )
    transaction = SimpleNamespace(
        authorization_url=(
            "https://checkout.paystack.test/current"
        ),
        access_code="current-access",
        provider_reference="MSF-CURRENT",
        payer_email="customer@example.com",
    )
    db = FakeSession(
        [
            order,
            build_store(order),
            transaction,
        ]
    )

    result = await initialize_payment(
        payload=PaymentInitializeRequest(
            order_id=order.id,
            customer_email="customer@example.com",
        ),
        db=db,
    )

    assert (
        result.authorization_url
        == transaction.authorization_url
    )
    assert result.reference == "MSF-CURRENT"
    assert db.commit_count == 0


@pytest.mark.asyncio
async def test_initialize_rejects_order_and_payload_email_mismatch(
    monkeypatch,
):
    configure_payment_dependencies(monkeypatch)

    order = build_order(
        customer_email="first@example.com"
    )
    db = FakeSession(
        [
            order,
            build_store(order),
        ]
    )

    with pytest.raises(HTTPException) as captured:
        await initialize_payment(
            payload=PaymentInitializeRequest(
                order_id=order.id,
                customer_email="second@example.com",
            ),
            db=db,
        )

    assert captured.value.status_code == 409
    assert (
        captured.value.detail
        == PAYMENT_LINK_EMAIL_MISMATCH_DETAIL
    )


@pytest.mark.asyncio
async def test_initialize_rejects_recorded_transaction_email_mismatch(
    monkeypatch,
):
    configure_payment_dependencies(monkeypatch)

    order = build_order()
    transaction = SimpleNamespace(
        authorization_url=(
            "https://checkout.paystack.test/current"
        ),
        access_code="current-access",
        provider_reference="MSF-CURRENT",
        payer_email="first@example.com",
    )
    db = FakeSession(
        [
            order,
            build_store(order),
            transaction,
        ]
    )

    with pytest.raises(HTTPException) as captured:
        await initialize_payment(
            payload=PaymentInitializeRequest(
                order_id=order.id,
                customer_email="second@example.com",
            ),
            db=db,
        )

    assert captured.value.status_code == 409
    assert (
        captured.value.detail
        == PAYMENT_LINK_EMAIL_MISMATCH_DETAIL
    )


@pytest.mark.asyncio
async def test_initialize_persists_exact_email_used_with_provider(
    monkeypatch,
):
    configure_payment_dependencies(monkeypatch)
    monkeypatch.setattr(
        payments_module.httpx,
        "AsyncClient",
        FakeAsyncClient,
    )

    order = build_order()
    db = FakeSession(
        [
            order,
            build_store(order),
            None,
        ]
    )

    result = await initialize_payment(
        payload=PaymentInitializeRequest(
            order_id=order.id,
            customer_email="Customer@Example.COM",
        ),
        db=db,
    )

    assert result.reference.startswith("MSF-")
    assert order.customer_email == "customer@example.com"
    assert db.commit_count == 1
    assert len(db.added) == 1

    transaction = db.added[0]

    assert isinstance(transaction, Transaction)
    assert transaction.payer_email == (
        "customer@example.com"
    )
    assert FakeAsyncClient.captured_payload["email"] == (
        "customer@example.com"
    )
