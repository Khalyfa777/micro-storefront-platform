from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from pydantic import ValidationError

from app.api.v1.payments import (
    initialize_payment,
    paystack_webhook,
    verify_payment,
)
from app.api.v1.public import (
    get_public_online_payment_flag,
)
from app.api.v1.stores import (
    get_store_subscription_usage,
)
from app.core.config import Settings, settings
from app.schemas.payment import (
    PaymentInitializeRequest,
)


DEPLOYED_SETTINGS = {
    "ENVIRONMENT": "production",
    "SECRET_KEY": "a" * 64,
    "FRONTEND_URL": "https://storeplughq.com",
    "DASHBOARD_PUBLIC_URL": (
        "https://dashboard.storeplughq.com"
    ),
    "BACKEND_PUBLIC_URL": (
        "https://api.storeplughq.com"
    ),
    "DATABASE_URL": (
        "postgresql+asyncpg://storeplug:"
        "strong-password@postgres:5432/storeplug_db"
    ),
    "REDIS_URL": "redis://redis:6379/0",
    "CORS_ORIGINS": (
        "https://storeplughq.com,"
        "https://dashboard.storeplughq.com"
    ),
}


class ExplodingSession:
    async def execute(self, statement):
        del statement
        raise AssertionError(
            "Database access must not occur."
        )


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value

    def scalar_one_or_none(self):
        return self.value


class FakeSession:
    def __init__(self, values):
        self.values = list(values)

    async def execute(self, statement):
        del statement

        if not self.values:
            raise AssertionError(
                "Unexpected database query."
            )

        return FakeResult(
            self.values.pop(0)
        )


def build_settings(**overrides):
    values = {
        **DEPLOYED_SETTINGS,
        "PAYMENTS_ENABLED": False,
        "PAYSTACK_SECRET_KEY": "",
        "PAYSTACK_PUBLIC_KEY": "",
    }
    values.update(overrides)

    return Settings(
        _env_file=None,
        **values,
    )


def assert_payment_unavailable(error):
    assert error.value.status_code == 503
    assert error.value.detail == (
        "Online payments are temporarily unavailable."
    )


def build_request():
    async def receive():
        raise AssertionError(
            "Request body must not be read."
        )

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/payments/webhook",
            "headers": [],
        },
        receive,
    )


def test_deployed_backend_allows_payments_to_be_disabled():
    configured = build_settings()

    assert configured.ENVIRONMENT == "production"
    assert configured.PAYMENTS_ENABLED is False
    assert configured.PAYSTACK_SECRET_KEY == ""
    assert configured.PAYSTACK_PUBLIC_KEY == ""


@pytest.mark.parametrize(
    ("secret_key", "public_key", "message"),
    [
        (
            "",
            "pk_live_public",
            "PAYSTACK_SECRET_KEY",
        ),
        (
            "sk_live_secret",
            "",
            "PAYSTACK_PUBLIC_KEY",
        ),
        (
            "sk_test_secret",
            "pk_live_public",
            "PAYSTACK_SECRET_KEY",
        ),
        (
            "sk_live_secret",
            "pk_test_public",
            "PAYSTACK_PUBLIC_KEY",
        ),
    ],
)
def test_deployed_enabled_payments_require_live_keys(
    secret_key,
    public_key,
    message,
):
    with pytest.raises(
        ValidationError,
        match=message,
    ):
        build_settings(
            PAYMENTS_ENABLED=True,
            PAYSTACK_SECRET_KEY=secret_key,
            PAYSTACK_PUBLIC_KEY=public_key,
        )


def test_deployed_enabled_payments_accept_live_keys():
    configured = build_settings(
        PAYMENTS_ENABLED=True,
        PAYSTACK_SECRET_KEY="sk_live_secret",
        PAYSTACK_PUBLIC_KEY="pk_live_public",
    )

    assert configured.PAYMENTS_ENABLED is True


@pytest.mark.asyncio
async def test_initialize_fails_before_database_when_disabled(
    monkeypatch,
):
    monkeypatch.setattr(
        settings,
        "PAYMENTS_ENABLED",
        False,
    )
    monkeypatch.setattr(
        settings,
        "PAYSTACK_SECRET_KEY",
        "",
    )

    with pytest.raises(HTTPException) as captured:
        await initialize_payment(
            payload=PaymentInitializeRequest(
                order_id=uuid4(),
            ),
            db=ExplodingSession(),
        )

    assert_payment_unavailable(captured)


@pytest.mark.asyncio
async def test_verify_fails_before_database_when_disabled(
    monkeypatch,
):
    monkeypatch.setattr(
        settings,
        "PAYMENTS_ENABLED",
        False,
    )
    monkeypatch.setattr(
        settings,
        "PAYSTACK_SECRET_KEY",
        "",
    )

    with pytest.raises(HTTPException) as captured:
        await verify_payment(
            reference="MSF-DISABLED",
            db=ExplodingSession(),
        )

    assert_payment_unavailable(captured)


@pytest.mark.asyncio
async def test_webhook_fails_before_body_or_database_when_disabled(
    monkeypatch,
):
    monkeypatch.setattr(
        settings,
        "PAYMENTS_ENABLED",
        False,
    )
    monkeypatch.setattr(
        settings,
        "PAYSTACK_SECRET_KEY",
        "",
    )

    with pytest.raises(HTTPException) as captured:
        await paystack_webhook(
            request=build_request(),
            db=ExplodingSession(),
        )

    assert_payment_unavailable(captured)


@pytest.mark.asyncio
async def test_public_payment_flag_fails_closed_without_plan_query(
    monkeypatch,
):
    monkeypatch.setattr(
        settings,
        "PAYMENTS_ENABLED",
        False,
    )

    available = await get_public_online_payment_flag(
        ExplodingSession(),
        SimpleNamespace(
            plan_name="starter",
        ),
    )

    assert available is False


@pytest.mark.asyncio
async def test_public_payment_flag_requires_platform_and_plan(
    monkeypatch,
):
    monkeypatch.setattr(
        settings,
        "PAYMENTS_ENABLED",
        True,
    )

    plan = SimpleNamespace(
        is_active=True,
        can_receive_online_payments=True,
    )

    available = await get_public_online_payment_flag(
        FakeSession([plan]),
        SimpleNamespace(
            plan_name="starter",
        ),
    )

    assert available is True


@pytest.mark.asyncio
async def test_seller_usage_reports_effective_payment_capability(
    monkeypatch,
):
    monkeypatch.setattr(
        settings,
        "PAYMENTS_ENABLED",
        False,
    )

    plan = SimpleNamespace(
        is_active=True,
        product_limit=10,
        display_name="Starter",
        monthly_fee=30,
        is_quote_only=False,
        can_upload_images=True,
        can_use_custom_domain=False,
        can_receive_online_payments=True,
    )

    response = await get_store_subscription_usage(
        store=SimpleNamespace(
            id=uuid4(),
            plan_name="starter",
            monthly_fee=30,
        ),
        db=FakeSession(
            [
                2,
                plan,
            ]
        ),
    )

    assert response.can_receive_online_payments is False
    assert response.plan_is_active is True
