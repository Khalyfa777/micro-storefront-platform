from datetime import (
    datetime,
    timezone,
)
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import (
    FastAPI,
    HTTPException,
)
from httpx import (
    ASGITransport,
    AsyncClient,
)
from starlette.requests import Request

from app.api.v1 import orders as orders_api
from app.db.session import get_db
from app.schemas.order import (
    PublicOrderCreate,
    PublicOrderTrackingResponse,
)
from app.services import (
    order_tracking_rate_limit,
)
from app.services.order_tracking import (
    normalize_customer_phone,
)


class BrokenRedis:
    async def eval(
        self,
        *args,
        **kwargs,
    ):
        raise ConnectionError(
            "Controlled Redis outage."
        )

    async def aclose(self):
        return None


class FakeResult:
    def __init__(
        self,
        row,
    ) -> None:
        self._row = row

    def first(self):
        return self._row


class FakeSession:
    def __init__(
        self,
        row,
    ) -> None:
        self._row = row

    async def execute(
        self,
        statement,
    ):
        del statement

        return FakeResult(self._row)


def make_request(
    ip_address: str = "203.0.113.55",
) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": (
                "/public/orders/track"
            ),
            "headers": [],
            "client": (
                ip_address,
                12345,
            ),
            "scheme": "http",
            "server": (
                "testserver",
                80,
            ),
        }
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "024 123 4567",
            "233241234567",
        ),
        (
            "+233 24 123 4567",
            "233241234567",
        ),
        (
            "00233-24-123-4567",
            "233241234567",
        ),
    ],
)
def test_phone_normalization(
    raw,
    expected,
):
    assert (
        normalize_customer_phone(raw)
        == expected
    )


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "abc",
        "123",
        "1" * 16,
    ],
)
def test_phone_normalization_rejects_invalid(
    raw,
):
    with pytest.raises(ValueError):
        normalize_customer_phone(raw)


def test_public_order_schema_stores_canonical_phone():
    payload = PublicOrderCreate(
        store_slug=" Demo-Store ",
        customer_name="  Test Customer  ",
        customer_phone="024 123 4567",
        items=[
            {
                "product_id": (
                    "00000000-0000-0000-"
                    "0000-000000000001"
                ),
                "quantity": 1,
            }
        ],
    )

    assert payload.store_slug == "demo-store"
    assert payload.customer_name == (
        "Test Customer"
    )
    assert payload.customer_phone == (
        "233241234567"
    )


def test_tracking_response_has_no_sensitive_fields():
    response = PublicOrderTrackingResponse(
        order_number="ORD-ABC1234567",
        store_slug="demo-store",
        status="pending",
        total=Decimal("120.00"),
        currency="GHS",
        items=[
            {
                "product_name": (
                    "Safe Product"
                ),
                "quantity": 1,
                "line_total": (
                    Decimal("120.00")
                ),
            }
        ],
        created_at=datetime.now(
            timezone.utc
        ),
    )

    fields = set(
        response.model_dump()
    )

    assert fields == {
        "order_number",
        "store_slug",
        "status",
        "total",
        "currency",
        "items",
        "created_at",
    }

    sensitive_fields = {
        "id",
        "store_id",
        "customer_name",
        "customer_phone",
        "customer_email",
        "delivery_address",
        "customer_note",
        "payment_method",
        "inventory_deducted",
        "is_oversold",
    }

    assert fields.isdisjoint(
        sensitive_fields
    )


def test_tracking_rate_limit_key_hides_ip():
    request = make_request(
        "203.0.113.55"
    )

    key = (
        order_tracking_rate_limit
        ._rate_limit_key(request)
    )

    assert "203.0.113.55" not in key

    assert key.startswith(
        "rate-limit:order-tracking:"
    )


@pytest.mark.asyncio
async def test_tracking_fallback_blocks(
    monkeypatch,
):
    monkeypatch.setattr(
        order_tracking_rate_limit,
        "_redis_client",
        lambda: BrokenRedis(),
    )

    (
        order_tracking_rate_limit
        ._fallback_buckets
        .clear()
    )

    (
        order_tracking_rate_limit
        ._last_fallback_log_at
    ) = 0.0

    request = make_request()

    for _ in range(
        order_tracking_rate_limit
        .TRACKING_LIMIT
    ):
        await (
            order_tracking_rate_limit
            .enforce_order_tracking_rate_limit(
                request
            )
        )

    with pytest.raises(
        HTTPException
    ) as error:
        await (
            order_tracking_rate_limit
            .enforce_order_tracking_rate_limit(
                request
            )
        )

    assert error.value.status_code == 429
    assert error.value.headers[
        "Retry-After"
    ]
    assert (
        "no-store"
        in error.value.headers[
            "Cache-Control"
        ]
    )

    (
        order_tracking_rate_limit
        ._fallback_buckets
        .clear()
    )


def make_order_row():
    item = SimpleNamespace(
        id="internal-item-id",
        product_id=(
            "internal-product-id"
        ),
        product_name="Safe Product",
        unit_price=Decimal("120.00"),
        quantity=1,
        line_total=Decimal("120.00"),
    )

    order = SimpleNamespace(
        id="internal-order-id",
        store_id="internal-store-id",
        order_number="ORD-ABC1234567",
        status="pending",
        payment_method=None,
        inventory_deducted=False,
        is_oversold=False,
        customer_name="Private Customer",
        customer_phone="024 123 4567",
        customer_email=(
            "private@example.com"
        ),
        delivery_address=(
            "Private address"
        ),
        customer_note="Private note",
        subtotal=Decimal("120.00"),
        delivery_fee=Decimal("0.00"),
        total=Decimal("120.00"),
        currency="GHS",
        items=[item],
        created_at=datetime(
            2026,
            7,
            13,
            tzinfo=timezone.utc,
        ),
    )

    return order, "demo-store"


async def allow_tracking_attempt(
    request,
):
    del request

    return None


@pytest.mark.asyncio
async def test_tracking_http_response_is_minimal(
    monkeypatch,
):
    monkeypatch.setattr(
        orders_api,
        "enforce_order_tracking_rate_limit",
        allow_tracking_attempt,
    )

    test_app = FastAPI()
    test_app.include_router(
        orders_api.router
    )

    row = make_order_row()

    async def override_get_db():
        yield FakeSession(row)

    test_app.dependency_overrides[
        get_db
    ] = override_get_db

    transport = ASGITransport(
        app=test_app
    )

    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/public/orders/track",
            json={
                "order_number": (
                    "ord-abc1234567"
                ),
                "customer_phone": (
                    "+233 24 123 4567"
                ),
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert set(data) == {
        "order_number",
        "store_slug",
        "status",
        "total",
        "currency",
        "items",
        "created_at",
    }

    serialized = str(data).lower()

    for forbidden_value in (
        "private customer",
        "private@example.com",
        "private address",
        "private note",
        "024 123 4567",
        "internal-order-id",
        "internal-store-id",
        "internal-product-id",
    ):
        assert (
            forbidden_value.lower()
            not in serialized
        )

    assert (
        "no-store"
        in response.headers[
            "cache-control"
        ]
    )

    test_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_tracking_http_mismatch_is_generic(
    monkeypatch,
):
    monkeypatch.setattr(
        orders_api,
        "enforce_order_tracking_rate_limit",
        allow_tracking_attempt,
    )

    test_app = FastAPI()
    test_app.include_router(
        orders_api.router
    )

    row = make_order_row()

    async def override_get_db():
        yield FakeSession(row)

    test_app.dependency_overrides[
        get_db
    ] = override_get_db

    transport = ASGITransport(
        app=test_app
    )

    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/public/orders/track",
            json={
                "order_number": (
                    "ORD-ABC1234567"
                ),
                "customer_phone": (
                    "055 000 0000"
                ),
            },
        )

    assert response.status_code == 404

    assert response.json() == {
        "detail": (
            "Order not found. Check the "
            "order number and phone number."
        )
    }

    assert (
        "no-store"
        in response.headers[
            "cache-control"
        ]
    )

    test_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_legacy_tracking_get_is_removed():
    test_app = FastAPI()
    test_app.include_router(
        orders_api.router
    )

    transport = ASGITransport(
        app=test_app
    )

    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            (
                "/public/orders/"
                "ORD-ABC1234567"
                "?customer_phone="
                "0241234567"
            )
        )

    assert response.status_code == 404
